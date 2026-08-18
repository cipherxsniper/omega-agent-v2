import os

os.environ["ANTHROPIC_API_KEY"] = "test-only-anthropic-key"

from api import claude_client


class Response:
    ok = True
    status_code = 200
    text = ""

    @staticmethod
    def json():
        return {
            "content": [
                {"type": "text", "text": "claude-ok"},
                {"type": "tool_use", "id": "tool-1", "name": "read_file", "input": {"path": "README.md"}},
            ]
        }


def main():
    captured = {}
    original = claude_client.requests.post

    def fake_post(url, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return Response()

    claude_client.requests.post = fake_post
    try:
        message = claude_client.chat_completion(
            [
                {"role": "system", "content": "Be precise."},
                {"role": "user", "content": [
                    {"type": "text", "text": "Inspect this."},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAAA"}},
                ]},
            ],
            tools=[{"type": "function", "function": {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            }}],
            return_message=True,
        )
    finally:
        claude_client.requests.post = original

    assert captured["headers"]["x-api-key"] == "test-only-anthropic-key"
    assert captured["json"]["system"] == "Be precise."
    assert captured["json"]["messages"][0]["content"][1]["type"] == "image"
    assert captured["json"]["tools"][0]["input_schema"]["type"] == "object"
    assert message["content"] == "claude-ok"
    assert message["tool_calls"][0]["function"]["name"] == "read_file"
    print("CLAUDE_ADAPTER_SMOKE_OK")


if __name__ == "__main__":
    main()
