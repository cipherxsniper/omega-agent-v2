import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.shadow_council import ActionProposal, ShadowCouncil, append_receipt
import json
import tempfile
from pathlib import Path


def council():
    return ShadowCouncil(
        allowed_roots=["/tmp/omega-root"],
        capabilities=["read_file", "write_file", "compile_code"],
    )


def test_safe_read_approves():
    decision = council().review(ActionProposal(
        action="read_file",
        capability="read_file",
        target="/tmp/omega-root/README.md",
        acceptance_tests=("receipt contains bytes_read",),
    ))
    assert decision.approved is True


def test_mutation_without_rollback_vetoes():
    decision = council().review(ActionProposal(
        action="write_file",
        capability="write_file",
        target="/tmp/omega-root/a.txt",
        mutation=True,
        acceptance_tests=("file exists",),
    ))
    assert decision.approved is False
    assert any(item.code == "NO_ROLLBACK" for item in decision.findings)


def test_shell_destructive_pattern_vetoes():
    decision = council().review(ActionProposal(
        action="run_bash",
        parameters={"command": "rm -rf /tmp/omega-root"},
        capability="run_bash",
    ))
    assert decision.approved is False
    assert any(item.code == "DANGEROUS_COMMAND" for item in decision.findings)


def test_outside_root_vetoes():
    decision = council().review(ActionProposal(
        action="read_file",
        capability="read_file",
        target="/etc/passwd",
    ))
    assert decision.approved is False
    assert any(item.code == "TARGET_OUTSIDE_ROOT" for item in decision.findings)


def test_unknown_capability_vetoes():
    decision = council().review(ActionProposal(action="network_call", capability="network_call"))
    assert decision.approved is False
    assert any(item.code == "UNKNOWN_CAPABILITY" for item in decision.findings)


def test_receipts_chain():
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "council.jsonl")
        first_council = council()
        first = append_receipt(path, first_council.review(ActionProposal(action="read_file", capability="read_file")))
        second = append_receipt(path, first_council.review(ActionProposal(action="compile_code", capability="compile_code")))
        assert second["previous_hash"] == first["receipt_hash"]
        assert len(Path(path).read_text().splitlines()) == 2
        json.loads(Path(path).read_text().splitlines()[0])


if __name__ == "__main__":
    test_safe_read_approves()
    test_mutation_without_rollback_vetoes()
    test_shell_destructive_pattern_vetoes()
    test_outside_root_vetoes()
    test_unknown_capability_vetoes()
    test_receipts_chain()
    print("SHADOW_COUNCIL_SMOKE_OK")
