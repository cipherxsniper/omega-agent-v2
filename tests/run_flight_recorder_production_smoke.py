import base64
import json
import os
import shutil
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main():
    private = Ed25519PrivateKey.generate()
    os.environ["PROOFCHAIN_SIGNING_KEY"] = base64.b64encode(private.private_bytes_raw()).decode()

    from agent.flight_recorder import FlightRecorder, production_cases
    from lib.omega_proof import verify_log

    out_dir = Path(tempfile.mkdtemp(prefix="omega-flight-production-"))
    try:
        recorder = FlightRecorder(out_dir, require_signed=True)
        production_cases(recorder, os.getenv("OMEGA_BACKEND_URL", "https://omega-agent-backend-v2.onrender.com"))
        report = recorder.write_report()
        public = private.public_key().public_bytes_raw()
        ok, message = verify_log(recorder.log_path, public)
        assert ok, message
        data = json.loads(report.read_text())
        assert data["total"] == 2
        assert data["failed"] == 0, data
        print("FLIGHT_RECORDER_PRODUCTION_SIGNED_SMOKE_OK")
        print(json.dumps({"score": data["score"], "cases": [c["case"] for c in data["cases"]]}))
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
