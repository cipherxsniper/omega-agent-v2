from dotenv import load_dotenv
load_dotenv()

import os
import time
import logging
import requests

from api import claude_client

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not set in environment")

# qwen/qwen3.6-27b: highest-reasoning model currently on Groq, supports
# reasoning_effort. Groq lists it as a preview model, so it may change
# or deprecate with less notice than the stable gpt-oss line.
DEFAULT_MODEL = "qwen/qwen3.6-27b"
FALLBACK_MODEL = "openai/gpt-oss-120b"  # stable, use if qwen3.6 errors/deprecates
FAST_MODEL = "openai/gpt-oss-20b"  # llama-3.1-8b-instant deprecated Aug 16 2026

# Tiered fallback stack, in priority order. Each has a separate daily quota
# on Groq, so if one tier is rate-limited for the day, we fall through to
# the next rather than blocking on a single model's TPD cap.
MODEL_TIER_STACK = [
    "qwen/qwen3.6-27b",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
]

# Per-model TPM ceilings on our current Groq tier (on_demand). Used to
# skip a tier pre-flight when the request clearly won't fit, instead of
# burning a call to discover that. Conservative/approximate - Groq's
# actual limit is the source of truth, this just avoids wasted round trips.
MODEL_TPM_LIMITS = {
    "llama-3.1-8b-instant": 6000,
}

def _estimate_tokens(messages, tools=None):
    """Rough token estimate (chars/4) for pre-flight TPM checks. Not
    exact - just needs to catch requests that are way over a small
    model's ceiling before we send them."""
    total_chars = sum(len(str(m)) for m in messages)
    if tools:
        total_chars += len(str(tools))
    return total_chars // 4

logger = logging.getLogger("GroqClient")

_STANDARD_MSG_KEYS = {"role", "content", "tool_calls", "tool_call_id", "name"}

def _sanitize_messages(messages):
    """Strip non-standard fields (e.g. 'reasoning' echoed back by some
    models like qwen) before replaying history against a different
    model tier. Groq's schema validation rejects unknown message
    fields on some models (llama-3.x), which was silently killing
    the whole fallback stack on 429s."""
    clean = []
    for m in messages:
        clean.append({k: v for k, v in m.items() if k in _STANDARD_MSG_KEYS})
    return clean
MAX_CALLS_PER_HOUR = int(os.environ.get("GROQ_MAX_CALLS_PER_HOUR", "120"))
_call_timestamps = []


def _check_rate_guard():
    now = time.time()
    cutoff = now - 3600
    while _call_timestamps and _call_timestamps[0] < cutoff:
        _call_timestamps.pop(0)
    if len(_call_timestamps) >= MAX_CALLS_PER_HOUR:
        raise RuntimeError(
            f"Groq call guard tripped: {len(_call_timestamps)} calls in the last hour "
            f"(limit {MAX_CALLS_PER_HOUR})."
        )
    _call_timestamps.append(now)
    if len(_call_timestamps) % 10 == 0:
        logger.info(f"Groq calls this hour: {len(_call_timestamps)}/{MAX_CALLS_PER_HOUR}")


def _post_once(payload):
    return requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )


def chat_completion(messages, model=None, temperature=0.3, max_tokens=2048,
                     tools=None, reasoning_effort=None, return_message=False,
                     _tier_start_index=0):
    """
    return_message=False (default): returns just the content string.
    return_message=True: returns the full message dict (includes tool_calls).

    Walks MODEL_TIER_STACK on rate-limit (429). A per-model daily-quota hit
    means retrying the SAME model is pointless until the quota window
    resets, so on 429 we move to the next tier immediately.
    """
    import re

    if _tier_start_index == 0 and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            claude_result = claude_client.chat_completion(
                messages,
                max_tokens=max_tokens,
                tools=tools,
                return_message=True,
            )
            return claude_result if return_message else claude_result.get("content", "")
        except Exception as exc:
            logger.warning("Claude primary failed; falling through to Groq: %s", exc)

    if not GROQ_API_KEY:
        raise RuntimeError("No model provider is configured: set ANTHROPIC_API_KEY or GROQ_API_KEY")

    has_images = any(
        isinstance(message.get("content"), list)
        and any(part.get("type") == "image_url" for part in message["content"] if isinstance(part, dict))
        for message in messages
        if isinstance(message, dict)
    )
    if has_images and model is None:
        # Only qwen/qwen3.6-27b is vision-capable in this configured stack.
        # Do not silently retry with text-only models and imply that an image was analyzed.
        tier = ["qwen/qwen3.6-27b"]
    else:
        tier = MODEL_TIER_STACK if model is None else [model] + [
            m for m in MODEL_TIER_STACK if m != model
        ]

    last_error = None
    for idx in range(_tier_start_index, len(tier)):
        current_model = tier[idx]

        tpm_limit = MODEL_TPM_LIMITS.get(current_model)
        if tpm_limit is not None:
            est = _estimate_tokens(messages, tools)
            if est > tpm_limit:
                logger.warning(
                    f"{current_model} skipped: est. {est} tokens exceeds "
                    f"{tpm_limit} TPM limit - would fail regardless of retries"
                )
                last_error = f"{current_model}: skipped, request (~{est}t) exceeds {tpm_limit} TPM"
                continue

        try:
            _check_rate_guard()
        except Exception as exc:
            last_error = f"{current_model}: local guard blocked request: {exc}"
            logger.warning(last_error)
            continue
        payload = {
            "model": current_model,
            "messages": _sanitize_messages(messages),
            "temperature": temperature,
        }
        if has_images:
            payload["max_completion_tokens"] = max_tokens
        else:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools
        if reasoning_effort:
            # Different model families support different reasoning_effort
            # vocab (or none at all). Normalize per-model here so every
            # caller can just pass one value and the tier stack keeps working
            # as new models are added.
            if current_model.startswith("qwen/"):
                payload["reasoning_effort"] = reasoning_effort  # 'none' or 'default'
            elif current_model.startswith("openai/gpt-oss"):
                # gpt-oss only accepts low/medium/high - map anything else to medium
                payload["reasoning_effort"] = reasoning_effort if reasoning_effort in (
                    "low", "medium", "high"
                ) else "medium"
            # llama-3.x models: reasoning_effort not supported at all - omit it

        try:
            resp = _post_once(payload)
        except requests.RequestException as exc:
            last_error = f"{current_model}: transport error: {exc}"
            logger.warning(last_error)
            continue
        except Exception as exc:
            last_error = f"{current_model}: unexpected request error: {exc}"
            logger.warning(last_error)
            continue

        if resp.status_code == 429:
            wait_match = re.search(r"try again in ([\d.]+)s", resp.text)
            wait_s = float(wait_match.group(1)) if wait_match else None
            is_daily_quota = "tokens per day" in resp.text or "TPD" in resp.text
            if is_daily_quota or idx < len(tier) - 1:
                logger.warning(
                    f"{current_model} rate limited"
                    + (f" (retry in {wait_s:.0f}s)" if wait_s else "")
                    + f" - falling through to next tier ({idx + 1}/{len(tier)} tried)"
                )
                last_error = f"{current_model}: {resp.text}"
                continue
            else:
                time.sleep(wait_s + 1.5 if wait_s else 15.0)
                try:
                    resp = _post_once(payload)
                except requests.RequestException as exc:
                    last_error = f"{current_model}: retry transport error: {exc}"
                    logger.warning(last_error)
                    continue

        if not resp.ok:
            error_text = resp.text[:1000]
            # Providers occasionally reject a model-specific optional field
            # while accepting the same request without it. Retry once with
            # only the rejected compatibility field removed/translated, then
            # continue the normal tier fallback if that still fails.
            retry_payload = None
            lowered = error_text.lower()
            if "reasoning_effort" in payload and "reasoning_effort" in lowered:
                retry_payload = dict(payload)
                retry_payload.pop("reasoning_effort", None)
            elif "max_tokens" in payload and "max_tokens" in lowered and "max_completion_tokens" in lowered:
                retry_payload = dict(payload)
                retry_payload["max_completion_tokens"] = retry_payload.pop("max_tokens")
            if retry_payload is not None:
                try:
                    compatibility_resp = _post_once(retry_payload)
                    if compatibility_resp.ok:
                        resp = compatibility_resp
                    else:
                        error_text = compatibility_resp.text[:1000]
                except requests.RequestException as exc:
                    error_text = f"compatibility retry transport error: {exc}"
            if not resp.ok:
                logger.warning(f"{current_model} failed ({resp.status_code}): {error_text[:200]}")
                last_error = f"{current_model}: {error_text}"
                continue

        try:
            message = resp.json()["choices"][0]["message"]
            if not isinstance(message, dict):
                raise ValueError("provider returned a non-object message")
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            last_error = f"{current_model}: malformed provider response: {exc}"
            logger.warning(last_error)
            continue
        if idx > 0:
            logger.info(f"Served by fallback tier: {current_model} (tier index {idx})")
        if return_message:
            return message
        return message["content"]

    raise RuntimeError(f"All {len(tier)} model tiers exhausted or failed. Last error: {last_error}")
