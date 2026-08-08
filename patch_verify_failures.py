path = "agent/agent_loop.py"
with open(path) as f:
    src = f.read()

anchor = '''            if not tool_calls:
                final_content = message.get("content", "")
                transcript.append({"step": step, "role": "assistant", "content": final_content, "final": True})
                if signed_log:
                    sign_event(signed_log, event_type="agent_final", data={"step": step, "content": final_content[:1000]})
                break'''

assert src.count(anchor) == 1, "anchor not found/not unique - aborting"

replacement = '''            if not tool_calls:
                final_content = message.get("content", "")

                # Ground-truth failure check. The model's own summary is not
                # trusted on its own - every prior tool call in this session
                # is re-inspected here, and any real failure gets appended
                # verbatim regardless of what the model claimed. This is the
                # only place fabricated "success" reporting gets caught,
                # since it runs on the raw transcript data, not the model's
                # narration of it.
                failed_calls = []
                for entry in transcript:
                    if entry.get("role") != "tool":
                        continue
                    result = entry.get("result", {})
                    output = result.get("output", {}) if isinstance(result, dict) else {}
                    is_failure = (
                        result.get("success") is False
                        or result.get("accepted") is False
                    )
                    if is_failure:
                        err = (
                            output.get("error")
                            if isinstance(output, dict) and output.get("error")
                            else result.get("reason", "unspecified failure")
                        )
                        failed_calls.append(f"- step {entry.get('step')}: {err}")

                if failed_calls:
                    final_content += (
                        "\\n\\n[SYSTEM-VERIFIED FAILURES - do not treat prior "
                        "narration as authoritative on these points]\\n"
                        + "\\n".join(failed_calls)
                    )

                transcript.append({"step": step, "role": "assistant", "content": final_content, "final": True})
                if signed_log:
                    sign_event(signed_log, event_type="agent_final", data={"step": step, "content": final_content[:1000]})
                break'''

src = src.replace(anchor, replacement, 1)

with open(path, "w") as f:
    f.write(src)

print("patched", path)
