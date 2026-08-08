import re

path = "agent/agent_loop.py"
with open(path) as f:
    src = f.read()

# --- Edit 1: capture the model's original narrative before any
# system-appended blocks get added to final_content, so we have
# something clean to check for contradictions against.
anchor1 = '''            if not tool_calls:
                final_content = message.get("content", "")'''

assert src.count(anchor1) == 1, "anchor1 not found/not unique - aborting"

replacement1 = '''            if not tool_calls:
                final_content = message.get("content", "")
                narrative_text = final_content  # pristine copy, before any system-appended blocks'''

src = src.replace(anchor1, replacement1, 1)

# --- Edit 2: after the verified-data block is built, parse real
# "name: number" pairs out of it and compare against what the model's
# own narrative claimed for the same names. A mismatch means the model
# stated a number that contradicts real tool output - that's caught
# and flagged at the TOP of the response, not just appended as a
# separate block the model's false claim could still overshadow.
anchor2 = '''                if verified_data:
                    final_content += (
                        "\\n\\n[SYSTEM-VERIFIED DATA - use these exact figures, "
                        "do not restate different numbers]\\n"
                        + "\\n".join(verified_data)
                    )'''

assert src.count(anchor2) == 1, "anchor2 not found/not unique - aborting"

replacement2 = '''                if verified_data:
                    final_content += (
                        "\\n\\n[SYSTEM-VERIFIED DATA - use these exact figures, "
                        "do not restate different numbers]\\n"
                        + "\\n".join(verified_data)
                    )

                    # Parse real "name: number" pairs out of the actual
                    # verified stdout, then check whether the model's own
                    # narrative claimed a *different* number for the same
                    # name. This catches fabrication even when a real tool
                    # result was available and simply ignored/overridden.
                    verified_numbers = {}
                    pair_re = re.compile(r"([A-Za-z0-9_\\-\\.]+):\\s*(\\d+)")
                    for entry in transcript:
                        if entry.get("role") != "tool":
                            continue
                        result = entry.get("result", {})
                        output = result.get("output", {}) if isinstance(result, dict) else {}
                        cmd = output.get("command", "") if isinstance(output, dict) else ""
                        if "wc -l" in cmd or ("find" in cmd and "-type f" in cmd):
                            stdout = output.get("stdout", "") if isinstance(output, dict) else ""
                            for name, num in pair_re.findall(stdout):
                                verified_numbers[name] = num

                    contradictions = []
                    for name, real_num in verified_numbers.items():
                        for claimed_name, claimed_num in pair_re.findall(narrative_text):
                            if claimed_name == name and claimed_num != real_num:
                                contradictions.append(
                                    f"- \\"{name}\\": model said {claimed_num}, "
                                    f"verified tool output says {real_num}"
                                )

                    if contradictions:
                        final_content = (
                            "[SYSTEM WARNING: the response below contains numbers "
                            "that contradict verified tool output. Do not trust the "
                            "narrative's figures - use SYSTEM-VERIFIED DATA below "
                            "instead.]\\n"
                            + "\\n".join(contradictions)
                            + "\\n\\n"
                            + final_content
                        )'''

src = src.replace(anchor2, replacement2, 1)

with open(path, "w") as f:
    f.write(src)

print("patched", path)
