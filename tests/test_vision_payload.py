import os

os.environ.setdefault("GROQ_API_KEY", "test-only-vision-key")

from api import groq_client


class Response:
    status_code = 200
    ok = True
    text = ""

    @staticmethod
    def json():
        return {"choices": [{"message": {"role": "assistant", "content": "image understood"}}]}


def main():
    captured = {}

    def fake_post(payload):
        captured.update(payload)
        return Response()

    original = groq_client._post_once
    groq_client._post_once = fake_post
    groq_client._call_timestamps.clear()
    try:
        result = groq_client.chat_completion(
            [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this."},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAAA"}},
                ],
            }],
            tools=[],
            max_tokens=256,
            return_message=True,
        )
    finally:
        groq_client._post_once = original

    assert result["content"] == "image understood"
    assert captured["model"] == "qwen/qwen3.6-27b"
    assert captured["max_completion_tokens"] == 256
    assert "max_tokens" not in captured
    print("VISION_PAYLOAD_SMOKE_OK")


if __name__ == "__main__":
    main()
