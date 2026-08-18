"""Optional native Anthropic Messages API adapter for Omega.

The adapter is dormant unless ANTHROPIC_API_KEY is configured. It never
creates, discovers, or prints credentials. Creator attribution: Thomas Lee Harvey.
"""

import json
import logging
import os
import re
from typing import Any

import requests

logger = logging.getLogger("ClaudeClient")
ANTHROPIC_API_URL = os.environ.get("ANTHROPIC_API_URL", "https://api.anthropic.com/v1/messages")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_VERSION = os.environ.get("ANTHROPIC_VERSION", "2023-06-01")


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")
    return "\n".join(
        str(block.get("text", ""))
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()


def _to_claude_content(content: Any) -> Any:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")
    blocks = []
    for part in content:
        if not isinstance(part, dict):
            continue
        kind = part.get("type")
        if kind == "text":
            blocks.append({"type": "text", "text": str(part.get("text", ""))})
        elif kind == "image_url":
            url = str((part.get("image_url") or {}).get("url", ""))
            match = re.fullmatch(r"data:(image/(?:jpeg|png|gif|webp));base64,(.+)", url, re.DOTALL)
            if match:
                blocks.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": match.group(1), "data": match.group(2)},
                })
            elif url.startswith("http://") or url.startswith("https://"):
                blocks.append({"type": "image", "source": {"type": "url", "url": url}})
        elif kind == "tool_result":
            blocks.append({
                "type": "tool_result",
                "tool_use_id": part.get("tool_use_id", ""),
                "content": str(part.get("content", "")),
            })
    return blocks or ""


def _convert_messages(messages):
    system_parts = []
    output = []
    for message in messages:
        role = message.get("role", "user")
        if role == "system":
            system_parts.append(_text_from_content(message.get("content", "")))
            continue
        if role == "tool":
            output.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": message.get("tool_call_id", ""),
                    "content": str(message.get("content", "")),
                }],
            })
            continue
        content = _to_claude_content(message.get("content", ""))
        if role == "assistant" and message.get("tool_calls"):
            blocks = []
            text = _text_from_content(content)
            if text:
                blocks.append({"type": "text", "text": text})
            for call in message["tool_calls"]:
                function = call.get("function", {})
                try:
                    arguments = json.loads(function.get("arguments", "{}"))
                except (TypeError, json.JSONDecodeError):
                    arguments = {}
                blocks.append({
                    "type": "tool_use",
                    "id": call.get("id", "omega_tool_call"),
                    "name": function.get("name", ""),
                    "input": arguments,
                })
            content = blocks
        output.append({"role": "assistant" if role == "assistant" else "user", "content": content})
    return system_parts, output


def _convert_tools(tools):
    converted = []
    for tool in tools or []:
        function = tool.get("function", tool)
        converted.append({
            "name": function.get("name", ""),
            "description": function.get("description", ""),
            "input_schema": function.get("parameters", {"type": "object", "properties": {}}),
        })
    return converted


def _normalize_response(payload):
    text_parts = []
    tool_calls = []
    for block in payload.get("content", []):
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))
        elif block.get("type") == "tool_use":
            tool_calls.append({
                "id": block.get("id", "omega_tool_call"),
                "type": "function",
                "function": {
                    "name": block.get("name", ""),
                    "arguments": json.dumps(block.get("input", {}), separators=(",", ":")),
                },
            })
    message = {"role": "assistant", "content": "\n".join(text_parts).strip()}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return message


def chat_completion(messages, max_tokens=2048, tools=None, return_message=False):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    system_parts, converted_messages = _convert_messages(messages)
    payload = {
        "model": os.environ.get("ANTHROPIC_MODEL", ANTHROPIC_MODEL),
        "max_tokens": max_tokens,
        "messages": converted_messages,
    }
    if system_parts:
        payload["system"] = "\n\n".join(part for part in system_parts if part)
    converted_tools = _convert_tools(tools)
    if converted_tools:
        payload["tools"] = converted_tools
    response = requests.post(
        ANTHROPIC_API_URL,
        headers={
            "x-api-key": key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(f"Claude request failed ({response.status_code}): {response.text[:300]}")
    normalized = _normalize_response(response.json())
    if return_message:
        return normalized
    return normalized.get("content", "")
