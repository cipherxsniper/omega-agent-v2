import os

os.environ.setdefault("GROQ_API_KEY", "test-import-only")

from agent import agent_loop
from agent.chat_server import _validate_images


def main():
    valid = _validate_images([{
        "name": "photo.jpg",
        "type": "image/jpeg",
        "dataUrl": "data:image/jpeg;base64," + ("A" * 64),
    }])
    assert valid[0]["name"] == "photo.jpg"

    try:
        _validate_images([{"name": "bad", "dataUrl": "https://example.invalid/photo.jpg"}])
    except ValueError:
        pass
    else:
        raise AssertionError("non-data image URL was accepted")

    original = agent_loop.chat_completion
    captured = {}

    def provider(messages, **kwargs):
        captured["messages"] = messages
        return {"role": "assistant", "content": "vision path observed", "tool_calls": []}

    agent_loop.chat_completion = provider
    try:
        transcript = agent_loop.run_agent_task(
            "Describe the attached image.", max_steps=1, image_inputs=valid
        )
    finally:
        agent_loop.chat_completion = original

    user_message = captured["messages"][-1]
    assert isinstance(user_message["content"], list)
    assert any(part.get("type") == "image_url" for part in user_message["content"])
    assert any(entry.get("final") and entry.get("content") == "vision path observed" for entry in transcript)
    print("IMAGE_CONTRACT_SMOKE_OK")


if __name__ == "__main__":
    main()
