"""Omega Mission Autopilot v1: bounded evidence-first autonomous missions.

Creator attribution: Thomas Lee Harvey.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Callable

from agent.shadow_council import ActionProposal, ShadowCouncil, stable_hash


@dataclass(frozen=True)
class Capability:
    name: str
    description: str
    mutation: bool = False
    requires_council: bool = True
    handler: Callable[[dict[str, Any]], dict[str, Any]] | None = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class MissionTask:
    task_id: str
    title: str
    capability: str
    inputs: dict[str, Any] = field(default_factory=dict)
    acceptance: tuple[str, ...] = ()
    retry_budget: int = 1
    mutation: bool = False
    rollback: str | None = None


@dataclass
class Mission:
    mission_id: str
    objective: str
    creator: str = "Thomas Lee Harvey"
    constraints: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    tasks: list[MissionTask] = field(default_factory=list)
    state: str = "proposed"
    events: list[dict[str, Any]] = field(default_factory=list)
    previous_hash: str | None = None


class MissionAutopilot:
    STATES = {"proposed", "council_review", "ready", "executing", "blocked", "completed", "failed"}

    def __init__(self, council: ShadowCouncil | None = None):
        self.capabilities: dict[str, Capability] = {}
        self.council = council
        self._register_core_capabilities()

    def register_capability(self, capability: Capability) -> None:
        if capability.name in self.capabilities:
            raise ValueError(f"capability already registered: {capability.name}")
        if capability.handler is None:
            raise ValueError("capability requires a real handler")
        self.capabilities[capability.name] = capability

    def create_mission(self, objective: str, acceptance_criteria: list[str] | tuple[str, ...], constraints: list[str] | tuple[str, ...] = ()) -> Mission:
        if not objective.strip():
            raise ValueError("mission objective is required")
        mission = Mission(str(uuid.uuid4()), objective.strip(), acceptance_criteria=tuple(item for item in acceptance_criteria if item.strip()), constraints=tuple(constraints))
        self._event(mission, "mission_created", {"objective_hash": stable_hash(objective), "acceptance_count": len(mission.acceptance_criteria)})
        return mission

    def add_task(self, mission: Mission, title: str, capability: str, inputs: dict[str, Any] | None = None, acceptance: list[str] | tuple[str, ...] = (), retry_budget: int = 1, mutation: bool = False, rollback: str | None = None) -> MissionTask:
        if mission.state not in {"proposed", "council_review", "ready"}:
            raise ValueError("tasks can only be added before execution")
        if capability not in self.capabilities:
            raise ValueError(f"unregistered capability: {capability}")
        if retry_budget < 0 or retry_budget > 3:
            raise ValueError("retry budget must be between 0 and 3")
        task = MissionTask(str(uuid.uuid4()), title, capability, inputs or {}, tuple(acceptance), retry_budget, mutation, rollback)
        mission.tasks.append(task)
        self._event(mission, "task_added", {"task_id": task.task_id, "capability": capability})
        return task

    def blind_spots(self, mission: Mission) -> list[str]:
        findings = []
        if not mission.acceptance_criteria:
            findings.append("MISSION_NO_ACCEPTANCE_CRITERIA")
        if not mission.tasks:
            findings.append("MISSION_NO_TASKS")
        for task in mission.tasks:
            if not task.acceptance:
                findings.append(f"TASK_NO_EVIDENCE:{task.task_id}")
            if task.mutation and not task.rollback:
                findings.append(f"MUTATION_NO_ROLLBACK:{task.task_id}")
            if task.capability not in self.capabilities:
                findings.append(f"TASK_UNKNOWN_CAPABILITY:{task.task_id}")
        return findings

    def review(self, mission: Mission) -> dict[str, Any]:
        mission.state = "council_review"
        blind_spots = self.blind_spots(mission)
        if blind_spots:
            self._event(mission, "mission_blocked", {"reason": "blind_spots", "findings": blind_spots})
            mission.state = "blocked"
            return {"approved": False, "reason": "blind_spots", "findings": blind_spots}
        vetoes = []
        for task in mission.tasks:
            capability = self.capabilities[task.capability]
            if capability.requires_council and self.council:
                decision = self.council.review(ActionProposal(
                    action=task.capability,
                    parameters={"mission_id": mission.mission_id, "task_id": task.task_id},
                    capability=task.capability,
                    mutation=task.mutation or capability.mutation,
                    rollback=task.rollback,
                    acceptance_tests=task.acceptance,
                ))
                self._event(mission, "council_review", {"task_id": task.task_id, "receipt": decision.receipt()})
                if not decision.approved:
                    vetoes.append(task.task_id)
        if vetoes:
            mission.state = "blocked"
            self._event(mission, "mission_blocked", {"reason": "council_veto", "task_ids": vetoes})
            return {"approved": False, "reason": "council_veto", "task_ids": vetoes}
        mission.state = "ready"
        self._event(mission, "mission_ready", {"task_count": len(mission.tasks)})
        return {"approved": True, "findings": []}

    def execute(self, mission: Mission) -> dict[str, Any]:
        if mission.state != "ready":
            raise ValueError(f"mission must be ready, got {mission.state}")
        mission.state = "executing"
        results = []
        for task in mission.tasks:
            capability = self.capabilities[task.capability]
            attempts = 0
            result = None
            while attempts <= task.retry_budget:
                attempts += 1
                try:
                    result = capability.handler(dict(task.inputs))
                    if not isinstance(result, dict):
                        raise TypeError("capability must return a dict evidence result")
                    break
                except Exception as exc:
                    result = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)[:300]}
            passed = bool(result and result.get("ok", False)) and all(result.get("evidence", {}).get(key) for key in task.acceptance)
            record = {"task_id": task.task_id, "capability": task.capability, "attempts": attempts, "passed": passed, "result": result}
            results.append(record)
            self._event(mission, "task_result", record)
            if not passed:
                mission.state = "failed"
                self._event(mission, "mission_failed", {"task_id": task.task_id})
                return {"status": "failed", "mission_id": mission.mission_id, "results": results, "receipt_hash": mission.previous_hash}
        mission.state = "completed"
        self._event(mission, "mission_completed", {"results": len(results)})
        return {"status": "completed", "mission_id": mission.mission_id, "results": results, "receipt_hash": mission.previous_hash}

    def _event(self, mission: Mission, kind: str, data: dict[str, Any]) -> None:
        event = {"kind": kind, "mission_id": mission.mission_id, "created_at": time.time(), "data": data, "previous_hash": mission.previous_hash}
        event["receipt_hash"] = hashlib.sha256(json.dumps(event, sort_keys=True, default=str).encode()).hexdigest()
        mission.previous_hash = event["receipt_hash"]
        mission.events.append(event)

    def _register_core_capabilities(self) -> None:
        self.register_capability(Capability("observe.constant", "Return bounded evidence supplied by the mission", False, False, lambda data: {"ok": True, "evidence": data}))
