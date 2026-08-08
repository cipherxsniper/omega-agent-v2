path = "agent/agent_loop.py"
with open(path) as f:
    src = f.read()

anchor = '''                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_json,
                })'''

assert src.count(anchor) == 1, "anchor not found/not unique - aborting"

replacement = '''                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": tc["function"]["name"],
                    "content": result_json,
                })'''

src = src.replace(anchor, replacement, 1)

with open(path, "w") as f:
    f.write(src)

print("patched", path)
