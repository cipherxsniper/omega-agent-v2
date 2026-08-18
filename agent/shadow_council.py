"""Omega Shadow Council: bounded pre-execution safety gate.

The council evaluates observable action contracts only. It does not execute
commands, mutate files, receive secrets, or expose private model reasoning.
Creator attribution: Thomas Lee Harvey.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

_SECRET_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password|private[_-]?key|authorization)\s*[:=]")
_DANGEROUS_COMMAND_RE = re.compile(r"(?i)(rm\s+-rf|mkfs|dd\s+if=|shutdown|reboot|:(){:|curl[^\n|]*\|\s*(sh|bash)|chmod\s+777)")


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ActionProposal:
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    target: str | None = None
    capability: str | None = None
    mutation: bool = False
    rollback: str | None = None
    acceptance_tests: tuple[str, ...] = ()
    expected_diff_hash: str | None = None
    parent_provenance_id: str | None = None

    def canonical(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CouncilFinding:
    severity: str
    code: str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CouncilDecision:
    decision_id: str
    proposal_hash: str
    approved: bool
    planner: dict[str, Any]
    critic: dict[str, Any]
    verifier: dict[str, Any]
    findings: tuple[CouncilFinding, ...]
    created_at: float
    previous_hash: str | None = None

    def receipt(self) -> dict[str, Any]:
        result = asdict(self)
        result["findings"] = [asdict(item) for item in self.findings]
        result["receipt_hash"] = stable_hash(result)
        return result


class Planner:
    """Builds a bounded, observable plan from an action proposal."""

    def prepare(self, proposal: ActionProposal) -> dict[str, Any]:
        tests = [test for test in proposal.acceptance_tests if isinstance(test, str) and test.strip()]
        return {
            "role": "planner",
            "action": proposal.action,
            "capability": proposal.capability,
            "mutation": proposal.mutation,
            "target": proposal.target,
            "acceptance_tests": tests,
            "rollback_declared": bool(proposal.rollback) if proposal.mutation else True,
            "proposal_hash": stable_hash(proposal.canonical()),
        }


class AdversarialCritic:
    """Read-only critic. Any hard finding is a veto."""

    def inspect(self, proposal: ActionProposal, allowed_roots: Iterable[str] = ()) -> dict[str, Any]:
        findings: list[CouncilFinding] = []
        serialized = json.dumps(proposal.canonical(), sort_keys=True, default=str)
        if _SECRET_RE.search(serialized):
            findings.append(CouncilFinding("hard", "SECRET_LIKE_INPUT", "Proposal contains secret-like field material."))
        if proposal.action == "run_bash":
            command = str(proposal.parameters.get("command", ""))
            if _DANGEROUS_COMMAND_RE.search(command):
                findings.append(CouncilFinding("hard", "DANGEROUS_COMMAND", "Command matches a destructive or remote-pipe pattern."))
            if not command.strip():
                findings.append(CouncilFinding("hard", "EMPTY_COMMAND", "Shell action has no concrete command."))
        if proposal.mutation and not proposal.rollback:
            findings.append(CouncilFinding("hard", "NO_ROLLBACK", "Mutation has no declared rollback."))
        if proposal.mutation and not proposal.acceptance_tests:
            findings.append(CouncilFinding("hard", "NO_ACCEPTANCE_TEST", "Mutation has no observable acceptance test."))
        if proposal.target and allowed_roots:
            target = os.path.realpath(os.path.abspath(os.path.expanduser(proposal.target)))
            roots = [os.path.realpath(os.path.abspath(os.path.expanduser(root))) for root in allowed_roots]
            if not any(target == root or target.startswith(root + os.sep) for root in roots):
                findings.append(CouncilFinding("hard", "TARGET_OUTSIDE_ROOT", "Target is outside the approved workspace roots."))
        return {
            "role": "adversarial_critic",
            "hard_veto": any(item.severity == "hard" for item in findings),
            "findings": [asdict(item) for item in findings],
            "read_only": True,
        }


class Verifier:
    """Checks capability, evidence, and declared acceptance requirements."""

    def verify(self, proposal: ActionProposal, planner_result: dict[str, Any], critic_result: dict[str, Any], capabilities: Iterable[str] = ()) -> dict[str, Any]:
        findings: list[CouncilFinding] = []
        known = set(capabilities)
        if proposal.capability and known and proposal.capability not in known:
            findings.append(CouncilFinding("hard", "UNKNOWN_CAPABILITY", "Capability is not registered."))
        if not proposal.action.strip():
            findings.append(CouncilFinding("hard", "EMPTY_ACTION", "Action name is empty."))
        if planner_result.get("proposal_hash") != stable_hash(proposal.canonical()):
            findings.append(CouncilFinding("hard", "PLAN_HASH_MISMATCH", "Planner output does not match the proposal."))
        if critic_result.get("hard_veto"):
            findings.append(CouncilFinding("hard", "CRITIC_VETO", "Adversarial critic issued a hard veto."))
        if proposal.expected_diff_hash and not re.fullmatch(r"[0-9a-f]{64}", proposal.expected_diff_hash):
            findings.append(CouncilFinding("hard", "INVALID_DIFF_HASH", "Expected diff hash is not a SHA-256 digest."))
        return {
            "role": "verifier",
            "approved": not any(item.severity == "hard" for item in findings),
            "findings": [asdict(item) for item in findings],
            "evidence_required": list(proposal.acceptance_tests),
            "read_only": True,
        }


class ShadowCouncil:
    """Coordinates the three roles and emits replayable, hash-chained receipts."""

    def __init__(self, *, allowed_roots: Iterable[str] = (), capabilities: Iterable[str] = (), previous_hash: str | None = None):
        self.allowed_roots = tuple(allowed_roots)
        self.capabilities = tuple(capabilities)
        self.previous_hash = previous_hash
        self.planner = Planner()
        self.critic = AdversarialCritic()
        self.verifier = Verifier()

    def review(self, proposal: ActionProposal) -> CouncilDecision:
        planned = self.planner.prepare(proposal)
        criticized = self.critic.inspect(proposal, self.allowed_roots)
        verified = self.verifier.verify(proposal, planned, criticized, self.capabilities)
        findings = tuple(CouncilFinding(**item) for item in criticized.get("findings", []) + verified.get("findings", []))
        approved = bool(verified.get("approved")) and not criticized.get("hard_veto") and not any(item.severity == "hard" for item in findings)
        material = {"proposal": proposal.canonical(), "planned": planned, "criticized": criticized, "verified": verified, "previous_hash": self.previous_hash}
        decision_id = stable_hash({"material": material, "time_ns": time.time_ns()})[:24]
        decision = CouncilDecision(decision_id, stable_hash(proposal.canonical()), approved, planned, criticized, verified, findings, time.time(), self.previous_hash)
        self.previous_hash = decision.receipt()["receipt_hash"]
        return decision


def append_receipt(path: str, decision: CouncilDecision) -> dict[str, Any]:
    """Atomically append a JSONL receipt without ever writing secrets from inputs."""
    receipt = decision.receipt()
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return receipt
