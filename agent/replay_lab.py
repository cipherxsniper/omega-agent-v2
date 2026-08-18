"""Omega Replay Laboratory: safe deterministic incident reproduction.

Creator attribution: Thomas Lee Harvey.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable

from agent.shadow_council import ActionProposal, ShadowCouncil, stable_hash

_SECRET_KEY = re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization|private[_-]?key|cookie)")
_SECRET_VALUE = re.compile(r"(?i)(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|gsk_[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._~+/=-]+)")
_ABSOLUTE_DEVICE = re.compile(r"^/data/data/|^/sdcard/|^/storage/emulated/|^/proc/|^/sys/")


def redact(value: Any, key: str = "") -> Any:
    if _SECRET_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item, key) for item in value]
    if isinstance(value, tuple):
        return [redact(item, key) for item in value]
    if isinstance(value, str):
        if _SECRET_VALUE.search(value) or _ABSOLUTE_DEVICE.search(value):
            return "[REDACTED]"
        return value[:4000]
    return value


@dataclass(frozen=True)
class ReplayCase:
    case_id: str
    incident_class: str
    handler: str
    input: dict[str, Any]
    expected: dict[str, Any]
    observed: dict[str, Any] | None = None
    repair: dict[str, Any] | None = None

    def canonical(self) -> dict[str, Any]:
        return redact(asdict(self))


class ReplayLaboratory:
    def __init__(self, council: ShadowCouncil | None = None, previous_hash: str | None = None):
        self.handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}
        self.council = council
        self.previous_hash = previous_hash

    def register(self, name: str, handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{1,63}", name):
            raise ValueError("invalid replay handler name")
        self.handlers[name] = handler

    def replay(self, case: ReplayCase) -> dict[str, Any]:
        safe_case = ReplayCase(case.case_id, case.incident_class, case.handler, redact(case.input), redact(case.expected), redact(case.observed), redact(case.repair))
        if safe_case.handler not in self.handlers:
            return self._receipt(safe_case, {"status": "blocked", "reason": "UNKNOWN_REPLAY_HANDLER"}, None)
        council_receipt = None
        if safe_case.repair and self.council:
            proposal = ActionProposal(
                action="replay_repair",
                parameters={"case_id": safe_case.case_id, "incident_class": safe_case.incident_class},
                capability="replay_repair",
                mutation=False,
                acceptance_tests=("replay reaches expected outcome",),
            )
            decision = self.council.review(proposal)
            council_receipt = decision.receipt()
            if not decision.approved:
                return self._receipt(safe_case, {"status": "blocked", "reason": "SHADOW_COUNCIL_VETO"}, council_receipt)
        try:
            actual = redact(self.handlers[safe_case.handler](safe_case.input))
            passed = stable_hash(actual) == stable_hash(safe_case.expected)
            result = {"status": "passed" if passed else "failed", "actual": actual, "expected": safe_case.expected}
        except Exception as exc:
            result = {"status": "error", "error_type": type(exc).__name__, "error": str(exc)[:500]}
        return self._receipt(safe_case, result, council_receipt)

    def _receipt(self, case: ReplayCase, result: dict[str, Any], council_receipt: dict[str, Any] | None) -> dict[str, Any]:
        body = {"case": case.canonical(), "result": result, "council": council_receipt, "previous_hash": self.previous_hash, "created_at": time.time()}
        body["case_hash"] = stable_hash(case.canonical())
        body["receipt_hash"] = stable_hash(body)
        self.previous_hash = body["receipt_hash"]
        return body


def append_replay_receipt(path: str, receipt: dict[str, Any]) -> None:
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt, sort_keys=True) + "\n")
        stream.flush()


if __name__ == "__main__":
    lab = ReplayLaboratory()
    lab.register("provider.timeout", lambda data: {"status": "fallback", "provider": data.get("fallback_provider")})
    print(json.dumps(lab.replay(ReplayCase("demo", "provider", "provider.timeout", {"fallback_provider": "local"}, {"status": "fallback", "provider": "local"})), indent=2))
