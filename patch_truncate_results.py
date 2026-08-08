path = "agent/agent_loop.py"
with open(path) as f:
    src = f.read()

anchor = '''                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, default=str),
                })'''

assert src.count(anchor) == 1, "anchor not found/not unique - aborting, paste this back"

replacement = '''                # Cap tool-result size before it enters history. This is
                # byte-based, not tied to today's file/repo counts, so it
                # keeps working as the empire grows and a single tool call
                # (e.g. reading a large source file) can't blow the token
                # budget on its own. Full result still goes in `transcript`
                # (line above) and signed_log - only what feeds back into
                # the model's context gets capped.
                MAX_TOOL_RESULT_CHARS = 3000
                result_json = json.dumps(result, default=str)
                if len(result_json) > MAX_TOOL_RESULT_CHARS:
                    result_json = (
                        result_json[:MAX_TOOL_RESULT_CHARS]
                        + f"... [truncated, {len(result_json)} chars total - "
                        + "full result available in transcript/signed_log]"
                    )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_json,
                })'''

src = src.replace(anchor, replacement, 1)

with open(path, "w") as f:
    f.write(src)

print("patched", path)
