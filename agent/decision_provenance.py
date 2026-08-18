"""Causal decision provenance for Omega tool executions.

This module is additive: it does not claim to expose private chain-of-thought.
It records observable execution metadata and a concise, verifiable selection basis.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Iterable


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def build_decision_provenance(
    *,
    action: str,
    arguments: dict,
    step: int,
    available_alternatives: Iterable[str],
    parent_id: str | None,
    observed_context: Any,
) -> dict:
    """Build an observable decision record without fabricating hidden reasoning."""
    context_hash = _stable_hash({"step": step, "context": observed_context})
    decision_id = _stable_hash({"action": action, "step": step, "context_hash": context_hash, "time": time.time_ns()})
    return {
        "decision_id": decision_id,
        "action_chosen": action,
        "available_alternatives": [name for name in available_alternatives if name != action],
        "selection_basis": "The model emitted this tool call after the observable transcript context.",
        "confidence": None,
        "causal_parent_id": parent_id,
        "step": step,
        "context_hash": context_hash,
        "arguments_hash": _stable_hash(arguments),
        "recorded_at": time.time(),
    }
