import os

os.environ.setdefault("GROQ_API_KEY", "test-import-only")
import agent.agent_loop as loop


def test_empty_provider_content_gets_truthful_final_message():
    os.makedirs(os.path.dirname(loop.SESSION_PATH), exist_ok=True)
    original_provider = loop.chat_completion

    def empty_provider(*args, **kwargs):
        return {"role": "assistant", "content": "", "tool_calls": []}

    loop.chat_completion = empty_provider
    try:
        transcript = loop.run_agent_task("completion regression", max_steps=1)
    finally:
        loop.chat_completion = original_provider
    final_entries = [entry for entry in transcript if entry.get("final")]
    assert final_entries
    assert final_entries[-1]["content"].strip()
    assert "no final narrative" in final_entries[-1]["content"]


if __name__ == "__main__":
    test_empty_provider_content_gets_truthful_final_message()
    print("EMPTY_FINAL_RESPONSE_REGRESSION_OK")
