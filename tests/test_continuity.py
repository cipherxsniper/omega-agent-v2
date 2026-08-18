import json
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.omega_continuity import build_manifest, verify_manifest


def test_manifest_and_verify():
    repo = Path(__file__).resolve().parents[1]
    manifest = build_manifest(repo)
    receipt = verify_manifest(repo, manifest, run_tests=False)
    assert receipt["status"] == "verified"
    assert receipt["observed_commit"] == manifest["commit"]
    assert all(item["ok"] for item in receipt["files"].values())


def test_mismatch_fails_closed():
    repo = Path(__file__).resolve().parents[1]
    manifest = build_manifest(repo)
    manifest["commit"] = "0" * 40
    receipt = verify_manifest(repo, manifest, run_tests=False)
    assert receipt["status"] == "failed_closed"
    assert "commit_mismatch" in receipt["findings"]


if __name__ == "__main__":
    test_manifest_and_verify()
    test_mismatch_fails_closed()
    print("CONTINUITY_ENGINE_SMOKE_OK")
