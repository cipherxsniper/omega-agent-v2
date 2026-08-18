"""Omega Reliability Flight Recorder.

Runs observable reliability contracts only. It never exposes hidden reasoning,
executes destructive actions, or invents success. Production probes are opt-in.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = Path(os.path.expanduser("~/.omega/flight-recorder"))

sys.path.insert(0, str(ROOT))
from agent.decision_provenance import build_decision_provenance
from lib.omega_proof import sign_event


class FlightRecorder:
    def __init__(self, out_dir: Path, require_signed: bool = True):
        self.out_dir = out_dir.expanduser()
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.replay_dir = self.out_dir / "replays"
        self.replay_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.out_dir / "flight-recorder-signed.jsonl"
        self.require_signed = require_signed
        self.run_id = f"flight_{uuid.uuid4().hex[:16]}"
        self.cases: list[dict[str, Any]] = []

    def _classify(self, exc: Exception) -> str:
        text = str(exc).lower()
        if "timeout" in text or "connection" in text or "http" in text:
            return "transport"
        if "signature" in text or "proof" in text or "chain" in text:
            return "proof"
        if "assert" in text or "contract" in text or "expected" in text:
            return "contract"
        return "implementation"

    def case(self, name: str, replay: dict[str, Any], fn: Callable[[], dict[str, Any]]):
        started = time.time()
        record: dict[str, Any] = {
            "run_id": self.run_id,
            "case": name,
            "replay": replay,
            "started_at": started,
        }
        try:
            result = fn()
            record.update({"status": "passed", "result": result})
        except Exception as exc:
            record.update({
                "status": "failed",
                "failure_class": self._classify(exc),
                "error": str(exc),
            })
            replay_path = self.replay_dir / f"{self.run_id}_{name}.json"
            replay_path.write_text(json.dumps({"case": name, **replay}, indent=2) + "\n")
            record["replay_file"] = str(replay_path)
        record["duration_ms"] = round((time.time() - started) * 1000, 2)
        self.cases.append(record)
        if self.require_signed:
            try:
                sign_event(self.log_path, "flight_recorder_case", record)
            except RuntimeError:
                raise RuntimeError(
                    "Proof signer is not configured. Set PROOFCHAIN_SIGNING_KEY or "
                    "PROOFCHAIN_KEYFILE; no unsigned production scorecard will be emitted."
                )
        return record

    def summary(self) -> dict[str, Any]:
        passed = sum(1 for case in self.cases if case["status"] == "passed")
        failed = len(self.cases) - passed
        score = round((passed / len(self.cases)) * 100, 2) if self.cases else 0.0
        return {
            "run_id": self.run_id,
            "created_by": "Thomas Lee Harvey",
            "score": score,
            "passed": passed,
            "failed": failed,
            "total": len(self.cases),
            "signed_log": str(self.log_path),
            "cases": self.cases,
        }

    def write_report(self) -> Path:
        report = self.out_dir / f"{self.run_id}.json"
        report.write_text(json.dumps(self.summary(), indent=2, default=str) + "\n")
        (self.out_dir / "latest.json").write_text(report.read_text())
        return report


def local_cases(recorder: FlightRecorder):
    def locking():
        result = subprocess.run(
            [sys.executable, str(ROOT / "tests/run_file_lock_smoke.py")],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0 or "FILE_LOCK_ATOMIC_WRITE_SMOKE_OK" not in result.stdout:
            raise AssertionError(result.stderr or result.stdout)
        return {"stdout": result.stdout.strip()}

    def completion():
        result = subprocess.run(
            [sys.executable, str(ROOT / "tests/test_empty_final_response.py")],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0 or "EMPTY_FINAL_RESPONSE_REGRESSION_OK" not in result.stdout:
            raise AssertionError(result.stderr or result.stdout)
        return {"stdout": result.stdout.strip()}

    def image_contract():
        result = subprocess.run(
            [sys.executable, str(ROOT / "tests/test_image_contract.py")],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0 or "IMAGE_CONTRACT_SMOKE_OK" not in result.stdout:
            raise AssertionError(result.stderr or result.stdout)
        return {"stdout": result.stdout.strip()}

    def provenance():
        first = build_decision_provenance(
            action="read_file", arguments={"path": "src/App.jsx"}, step=0,
            available_alternatives=["read_file", "run_bash"], parent_id=None,
            observed_context=[],
        )
        second = build_decision_provenance(
            action="compile_code", arguments={"path": "agent/agent_loop.py"}, step=1,
            available_alternatives=["compile_code", "run_bash"], parent_id=first["decision_id"],
            observed_context=[first],
        )
        assert second["causal_parent_id"] == first["decision_id"]
        assert first["context_hash"] != second["context_hash"]
        return {"root": first["decision_id"], "child": second["decision_id"]}

    recorder.case("file_locking", {"command": "tests/run_file_lock_smoke.py"}, locking)
    recorder.case("empty_final_response", {"command": "tests/test_empty_final_response.py"}, completion)
    recorder.case("image_contract", {"command": "tests/test_image_contract.py"}, image_contract)
    recorder.case("decision_provenance", {"operation": "build observable causal chain"}, provenance)


def production_cases(recorder: FlightRecorder, base_url: str):
    def health():
        response = requests.get(f"{base_url}/api/health", timeout=30)
        response.raise_for_status()
        payload = response.json()
        assert payload.get("status") == "ok", payload
        return payload

    def completion():
        response = requests.post(
            f"{base_url}/api/chat",
            json={"message": "Reply with exactly OK.", "max_steps": 1},
            timeout=90,
        )
        response.raise_for_status()
        payload = response.json()
        assert payload.get("response", "").strip(), payload
        return {"response": payload["response"], "transcript_count": len(payload.get("transcript", []))}

    recorder.case("production_health", {"method": "GET", "path": "/api/health"}, health)
    recorder.case("production_completion", {"method": "POST", "path": "/api/chat", "message": "Reply with exactly OK."}, completion)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--backend", default=os.getenv("OMEGA_BACKEND_URL", "https://omega-agent-backend-v2.onrender.com"))
    parser.add_argument("--allow-unsigned", action="store_true", help="testing only; never use for production scorecards")
    args = parser.parse_args()

    recorder = FlightRecorder(Path(args.out), require_signed=not args.allow_unsigned)
    local_cases(recorder)
    if args.production:
        production_cases(recorder, args.backend.rstrip("/"))
    report = recorder.write_report()
    print(json.dumps(recorder.summary(), indent=2))
    print(f"FLIGHT_RECORDER_REPORT={report}")
    if recorder.summary()["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
