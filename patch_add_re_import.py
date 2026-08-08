path = "agent/agent_loop.py"
with open(path) as f:
    src = f.read()

anchor = "import asyncio\n"
assert src.count(anchor) == 1, "anchor not found/not unique - aborting"

src = src.replace(anchor, anchor + "import re\n", 1)

with open(path, "w") as f:
    f.write(src)

print("patched", path)
