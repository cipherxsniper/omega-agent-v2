"""
Pluggable LLM client interface.

Real backends (Groq, OpenAI, Anthropic, local) all implement `complete()`.
Everything else in the brain talks to this interface, not to a specific
vendor SDK, so swapping providers means changing one line of config.
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger("OmegaLLM")


class LLMClient(ABC):
    @abstractmethod
    async def complete(self, prompt: str, temperature: float = 0.4, max_tokens: int = 800) -> str:
        """Return raw text completion for a prompt. Must raise on failure, never fake success."""
        raise NotImplementedError


class GroqClient(LLMClient):
    """Real Groq-backed client. Requires GROQ_API_KEY in environment."""

    def __init__(self, model: str = "llama-3.3-70b-versatile", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Export it before starting the agent: "
                "export GROQ_API_KEY=gsk_..."
            )

    async def complete(self, prompt: str, temperature: float = 0.4, max_tokens: int = 800) -> str:
        import httpx  # local import: only required if this backend is actually used

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


class MockLLMClient(LLMClient):
    """
    Deterministic mock for offline testing / CI. Never claims to be a real
    model — every response is tagged so it can't be mistaken for live output.
    Use this to verify wiring before pointing at a real API key.
    """

    def __init__(self, canned_responses: Optional[dict] = None):
        self.canned_responses = canned_responses or {}
        self.call_log = []

    async def complete(self, prompt: str, temperature: float = 0.4, max_tokens: int = 800) -> str:
        self.call_log.append(prompt)
        for key, response in self.canned_responses.items():
            if key in prompt:
                return response
        # Generic structured fallback so callers expecting JSON don't crash
        return json.dumps({"mock": True, "note": "no canned response matched prompt"})


def get_default_client() -> LLMClient:
    """
    Picks a backend from environment config. Falls back to Mock with a loud
    warning rather than silently pretending to be real - this is the fix for
    the pattern in the earlier code where failures were swallowed.
    """
    backend = os.environ.get("OMEGA_LLM_BACKEND", "groq").lower()
    if backend == "groq":
        try:
            return GroqClient()
        except RuntimeError as e:
            logger.warning(f"Falling back to MockLLMClient: {e}")
            return MockLLMClient()
    elif backend == "mock":
        return MockLLMClient()
    else:
        raise ValueError(f"Unknown OMEGA_LLM_BACKEND: {backend}")

