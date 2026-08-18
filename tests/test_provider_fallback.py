import os

os.environ.setdefault("GROQ_API_KEY", "test-only-provider-key")

import requests
from api import groq_client


class Response:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def run_transport_fallback():
    calls = []

    def fake_post(payload):
        calls.append(payload["model"])
        if len(calls) == 1:
            raise requests.Timeout("simulated provider timeout")
        return Response(payload={"choices": [{"message": {"role": "assistant", "content": "fallback-ok"}}]})

    groq_client._post_once = fake_post
    groq_client._call_timestamps.clear()
    result = groq_client.chat_completion(
        [{"role": "user", "content": "test"}],
        return_message=True,
    )
    assert result["content"] == "fallback-ok"
    assert calls[:2] == groq_client.MODEL_TIER_STACK[:2], calls


def run_malformed_fallback():
    calls = []

    def fake_post(payload):
        calls.append(payload["model"])
        if len(calls) == 1:
            return Response(payload={"unexpected": True})
        return Response(payload={"choices": [{"message": {"role": "assistant", "content": "json-fallback-ok"}}]})

    groq_client._post_once = fake_post
    groq_client._call_timestamps.clear()
    result = groq_client.chat_completion(
        [{"role": "user", "content": "test"}],
        return_message=True,
    )
    assert result["content"] == "json-fallback-ok"
    assert calls[:2] == groq_client.MODEL_TIER_STACK[:2], calls


if __name__ == "__main__":
    run_transport_fallback()
    run_malformed_fallback()
    print("PROVIDER_FALLBACK_CHAOS_SMOKE_OK")
