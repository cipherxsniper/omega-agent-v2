import re

path = "api/groq_client.py"
with open(path) as f:
    src = f.read()

anchor1 = 'logger = logging.getLogger("GroqClient")'
sanitize_fn = '''logger = logging.getLogger("GroqClient")

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
    return clean'''

assert src.count(anchor1) == 1, "anchor1 not unique, aborting"
src = src.replace(anchor1, sanitize_fn, 1)

anchor2 = '"messages": messages,'
assert src.count(anchor2) == 1, "anchor2 not unique, aborting"
src = src.replace(anchor2, '"messages": _sanitize_messages(messages),', 1)

with open(path, "w") as f:
    f.write(src)

print("patched", path)
