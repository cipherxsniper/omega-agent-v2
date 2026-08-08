path = "agent/agent_loop.py"
with open(path) as f:
    src = f.read()

anchor = '''                if failed_calls:
                    final_content += (
                        "\\n\\n[SYSTEM-VERIFIED FAILURES - do not treat prior "
                        "narration as authoritative on these points]\\n"
                        + "\\n".join(failed_calls)
                    )'''

assert src.count(anchor) == 1, "anchor not found/not unique - aborting"

replacement = anchor + '''

                # Ground any counting/verification commands the same way -
                # ensures claimed numbers in the final response actually
                # came from a real tool call, not the model's guess.
                verified_data = []
                for entry in transcript:
                    if entry.get("role") != "tool":
                        continue
                    result = entry.get("result", {})
                    output = result.get("output", {}) if isinstance(result, dict) else {}
                    cmd = output.get("command", "") if isinstance(output, dict) else ""
                    if "wc -l" in cmd or ("find" in cmd and "-type f" in cmd):
                        stdout = output.get("stdout", "").strip()
                        if stdout:
                            verified_data.append(f"- step {entry.get('step')}: `{cmd}` -> {stdout}")

                if verified_data:
                    final_content += (
                        "\\n\\n[SYSTEM-VERIFIED DATA - use these exact figures, "
                        "do not restate different numbers]\\n"
                        + "\\n".join(verified_data)
                    )'''

src = src.replace(anchor, replacement, 1)

with open(path, "w") as f:
    f.write(src)

print("patched", path)
