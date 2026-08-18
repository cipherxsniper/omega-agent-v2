import base64
import json
import os
import shutil
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main():
    private = Ed25519PrivateKey.generate()
    raw = private.private_bytes_raw()
    os.environ["PROOFCHAIN_SIGNING_KEY"] = base64.b64encode(raw).decode()

    from agent.flight_recorder import FlightRecorder, local_cases
    from lib.omega_proof import verify_log

    out_dir = Path(tempfile.mkdtemp(prefix="omega-flight-smoke-"))
    try:
        recorder = FlightRecorder(out_dir, require_signed=True)
        local_cases(recorder)
        failed = recorder.case(
            "synthetic_contract_failure",
            {"operation": "intentional test failure"},
            lambda: (_ for _ in ()).throw(AssertionError("expected contract mismatch")),
        )
        assert failed["status"] == "failed"
        assert failed["failure_class"] == "contract"
        assert Path(failed["replay_file"]).exists()
        report = recorder.write_report()
        public = private.public_key().public_bytes_raw()
        ok, message = verify_log(recorder.log_path, public)
        assert ok, message
        data = json.loads(report.read_text())
        assert data["score"] == 80.0
        assert data["total"] == 5
        assert data["failed"] == 1
        assert len(recorder.log_path.read_text().splitlines()) == 5
        print("FLIGHT_RECORDER_SIGNED_SMOKE_OK")
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
