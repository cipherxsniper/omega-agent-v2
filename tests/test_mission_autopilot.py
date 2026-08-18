import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.mission_autopilot import Capability, MissionAutopilot
from agent.shadow_council import ShadowCouncil


def test_completed_mission_has_receipts():
    autopilot = MissionAutopilot()
    mission = autopilot.create_mission("prove local evidence", ["ok"])
    autopilot.add_task(mission, "observe", "observe.constant", {"ok": True}, ["ok"])
    assert autopilot.review(mission)["approved"] is True
    result = autopilot.execute(mission)
    assert result["status"] == "completed"
    assert mission.state == "completed"
    assert len(mission.events) >= 4
    assert mission.events[-1]["receipt_hash"] == result["receipt_hash"]


def test_blind_spot_blocks():
    autopilot = MissionAutopilot()
    mission = autopilot.create_mission("missing evidence", [])
    autopilot.add_task(mission, "observe", "observe.constant", {"ok": True}, [])
    decision = autopilot.review(mission)
    assert decision["approved"] is False
    assert mission.state == "blocked"
    assert "MISSION_NO_ACCEPTANCE_CRITERIA" in decision["findings"]


def test_veto_blocks_mutation():
    council = ShadowCouncil(capabilities=["unsafe.write"])
    autopilot = MissionAutopilot(council=council)
    autopilot.register_capability(Capability("unsafe.write", "mutation", mutation=True, handler=lambda data: {"ok": True, "evidence": {"ok": True}}))
    mission = autopilot.create_mission("unsafe mutation", ["ok"])
    autopilot.add_task(mission, "write", "unsafe.write", {}, ["ok"], mutation=True)
    decision = autopilot.review(mission)
    assert decision["approved"] is False
    assert decision["reason"] == "blind_spots"


def test_retry_then_success():
    calls = {"count": 0}
    def flaky(data):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("transient")
        return {"ok": True, "evidence": {"ok": True}}
    autopilot = MissionAutopilot()
    autopilot.register_capability(Capability("test.flaky", "test", False, False, flaky))
    mission = autopilot.create_mission("recover", ["ok"])
    autopilot.add_task(mission, "retry", "test.flaky", {}, ["ok"], retry_budget=1)
    autopilot.review(mission)
    assert autopilot.execute(mission)["status"] == "completed"
    assert calls["count"] == 2


if __name__ == "__main__":
    test_completed_mission_has_receipts()
    test_blind_spot_blocks()
    test_veto_blocks_mutation()
    test_retry_then_success()
    print("MISSION_AUTOPILOT_SMOKE_OK")
