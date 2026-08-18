#!/usr/bin/env python3
"""Omega Continuity Engine: manifest-driven repository/device verification.

Creator attribution: Thomas Lee Harvey.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable

DEFAULT_FILES = (
    "tools/omega_reliability_audit.py",
    "agent/shadow_council.py",
    "agent/replay_lab.py",
    "agent/agent_loop.py",
    "tests/test_reliability_audit.py",
    "tests/test_shadow_council.py",
    "tests/test_replay_lab.py",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def build_manifest(repo: Path, files: Iterable[str] = DEFAULT_FILES) -> dict[str, Any]:
    commit = git(repo, "rev-parse", "HEAD")
    inventory = {}
    for relative in files:
        path = repo / relative
        if not path.is_file():
            raise FileNotFoundError(relative)
        inventory[relative] = sha256_file(path)
    manifest = {
        "schema": "omega-continuity/v1",
        "creator": "Thomas Lee Harvey",
        "repository": git(repo, "config", "--get", "remote.origin.url") or "unknown",
        "commit": commit,
        "files": inventory,
        "created_at": time.time(),
    }
    manifest["manifest_sha256"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    return manifest


def verify_manifest(repo: Path, manifest: dict[str, Any], run_tests: bool = True) -> dict[str, Any]:
    findings: list[str] = []
    try:
        observed_commit = git(repo, "rev-parse", "HEAD")
    except Exception as exc:
        observed_commit = None
        findings.append(f"git_unavailable:{type(exc).__name__}")
    if observed_commit != manifest.get("commit"):
        findings.append("commit_mismatch")
    file_results = {}
    for relative, expected in manifest.get("files", {}).items():
        path = repo / relative
        actual = sha256_file(path) if path.is_file() else None
        file_results[relative] = {"expected": expected, "actual": actual, "ok": actual == expected}
        if actual != expected:
            findings.append(f"file_mismatch:{relative}")
    tests = []
    if run_tests:
        commands = [
            ["python3", "-m", "py_compile", "tools/omega_reliability_audit.py", "agent/shadow_council.py", "agent/replay_lab.py", "agent/agent_loop.py"],
            ["python3", "tests/test_reliability_audit.py"],
            ["python3", "tests/test_shadow_council.py"],
            ["python3", "tests/test_replay_lab.py"],
        ]
        for command in commands:
            env = dict(os.environ, PYTHONPATH=".")
            result = subprocess.run(command, cwd=repo, capture_output=True, text=True, timeout=60, env=env)
            tests.append({"command": command, "returncode": result.returncode, "stdout": result.stdout[-1000:], "stderr": result.stderr[-1000:]})
            if result.returncode:
                findings.append("test_failure:" + command[-1])
    return {
        "schema": "omega-continuity-receipt/v1",
        "creator": "Thomas Lee Harvey",
        "verified_at": time.time(),
        "manifest_sha256": manifest.get("manifest_sha256"),
        "expected_commit": manifest.get("commit"),
        "observed_commit": observed_commit,
        "files": file_results,
        "tests": tests,
        "status": "verified" if not findings else "failed_closed",
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate or verify Omega continuity manifests")
    parser.add_argument("repo", nargs="?", default=".")
    parser.add_argument("--manifest", default="omega_continuity_manifest.json")
    parser.add_argument("--receipt", default="omega_continuity_receipt.json")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--no-tests", action="store_true")
    args = parser.parse_args(argv)
    repo = Path(args.repo).expanduser().resolve()
    manifest_path = repo / args.manifest
    if args.generate or not manifest_path.exists():
        manifest = build_manifest(repo)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(f"MANIFEST_WRITTEN={manifest_path}")
    else:
        manifest = json.loads(manifest_path.read_text())
    receipt = verify_manifest(repo, manifest, run_tests=not args.no_tests)
    (repo / args.receipt).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(f"RECEIPT_WRITTEN={repo / args.receipt}")
    print(json.dumps({"status": receipt["status"], "commit": receipt["observed_commit"], "findings": receipt["findings"]}, sort_keys=True))
    return 0 if receipt["status"] == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
