import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.replay_lab import ReplayCase, ReplayLaboratory, append_replay_receipt
from agent.shadow_council import ShadowCouncil


def test_replay_and_redaction():
    lab = ReplayLaboratory()
    lab.register("provider.timeout", lambda data: {"status": "fallback", "provider": data["fallback_provider"]})
    case = ReplayCase("case-1", "provider", "provider.timeout", {"fallback_provider": "claude", "api_key": "sk-SECRET"}, {"status": "fallback", "provider": "claude"})
    receipt = lab.replay(case)
    assert receipt["result"]["status"] == "passed"
    assert receipt["case"]["input"]["api_key"] == "[REDACTED]"


def test_unknown_handler_blocks():
    receipt = ReplayLaboratory().replay(ReplayCase("case-2", "ui", "missing", {}, {}))
    assert receipt["result"]["status"] == "blocked"


def test_repair_veto():
    council = ShadowCouncil(capabilities=["replay_repair"])
    lab = ReplayLaboratory(council=council)
    lab.register("safe.echo", lambda data: data)
    case = ReplayCase("case-3", "ui", "safe.echo", {"ok": True}, {"ok": True}, repair={"rollback": None})
    # replay_repair is non-mutating and has a concrete acceptance test, so it is approved.
    assert lab.replay(case)["result"]["status"] == "passed"


def test_receipt_chain():
    lab = ReplayLaboratory()
    lab.register("safe.echo", lambda data: data)
    first = lab.replay(ReplayCase("a", "test", "safe.echo", {"x": 1}, {"x": 1}))
    second = lab.replay(ReplayCase("b", "test", "safe.echo", {"x": 2}, {"x": 2}))
    assert second["previous_hash"] == first["receipt_hash"]


if __name__ == "__main__":
    test_replay_and_redaction()
    test_unknown_handler_blocks()
    test_repair_veto()
    test_receipt_chain()
    print("REPLAY_LAB_SMOKE_OK")
