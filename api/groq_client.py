from dotenv import load_dotenv
load_dotenv()

import os
import time
import logging
import requests

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

logger = logging.getLogger("GroqClient")
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


def chat_completion(messages, model=DEFAULT_MODEL, temperature=0.3, max_tokens=2048,
                     tools=None, reasoning_effort=None, return_message=False):
    """
    return_message=False (default, unchanged behavior): returns just the
    content string, for existing callers.
    return_message=True: returns the full message dict (includes tool_calls
    if the model made any) — needed for real agentic tool-use loops.
    """
    _check_rate_guard()
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools
    if reasoning_effort:
        # qwen3 models: 'none' or 'default'. gpt-oss models: 'low'/'medium'/'high'.
        payload["reasoning_effort"] = reasoning_effort

    resp = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    import re
    max_rate_retries = 5
    rate_retry = 0
    while resp.status_code == 429 and rate_retry < max_rate_retries:
        rate_retry += 1
        wait_match = re.search(r"try again in ([\d.]+)s", resp.text)
        wait_s = float(wait_match.group(1)) + 1.5 if wait_match else 15.0
        logger.warning(f"Rate limited (attempt {rate_retry}/{max_rate_retries}), waiting {wait_s:.1f}s...")
        time.sleep(wait_s)
        resp = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
    if resp.status_code == 429:
        raise RuntimeError(f"Groq still rate limited after {max_rate_retries} retries: {resp.text}")
    if not resp.ok:
        # Preview model may go away without notice — fall back once automatically.
        if model == DEFAULT_MODEL:
            logger.warning(f"{DEFAULT_MODEL} failed ({resp.status_code}), retrying with {FALLBACK_MODEL}")
            return chat_completion(messages, model=FALLBACK_MODEL, temperature=temperature,
                                    max_tokens=max_tokens, tools=tools, return_message=return_message)
        raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text}")

    message = resp.json()["choices"][0]["message"]
    if return_message:
        return message
    return message["content"]
