path = "api/groq_client.py"
with open(path) as f:
    src = f.read()

anchor1 = "MODEL_TIER_STACK = [\n    \"qwen/qwen3.6-27b\",\n    \"llama-3.3-70b-versatile\",\n    \"openai/gpt-oss-120b\",\n    \"openai/gpt-oss-20b\",\n    \"llama-3.1-8b-instant\",\n]"
assert src.count(anchor1) == 1, "anchor1 not found/not unique"

addition = anchor1 + '''

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
    return total_chars // 4'''

src = src.replace(anchor1, addition, 1)

anchor2 = "    for idx in range(_tier_start_index, len(tier)):\n        current_model = tier[idx]\n        _check_rate_guard()"
assert src.count(anchor2) == 1, "anchor2 not found/not unique"

replacement2 = '''    for idx in range(_tier_start_index, len(tier)):
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

        _check_rate_guard()'''

src = src.replace(anchor2, replacement2, 1)

with open(path, "w") as f:
    f.write(src)

print("patched", path)
