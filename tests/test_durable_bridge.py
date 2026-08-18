import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "device_bridge" / "omega_bridge_server.py"


def request(url, token, method="GET", body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as response:
        return response.status, json.loads(response.read())


def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "agent").mkdir()
        (root / "agent" / "chat_server.py").write_text("before")
        token_file = root / ".omega-bridge" / "token"
        token_file.parent.mkdir()
        token_file.write_text("bridge-test-token\n")
        env = os.environ.copy()
        env.update({
            "OMEGA_BRIDGE_ROOT": str(root),
            "OMEGA_BRIDGE_TOKEN_FILE": str(token_file),
            "OMEGA_BRIDGE_PORT": "18791",
            "PYTHONPATH": str(ROOT),
        })
        process = subprocess.Popen(["python3", str(SERVER)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            time.sleep(0.2)
            status, health = request("http://127.0.0.1:18791/health", "bridge-test-token")
            assert status == 200
            assert "syntax" in health["capabilities"]

            try:
                request("http://127.0.0.1:18791/v1/read", "bridge-test-token", "POST", {"path": "../../etc/passwd"})
            except urllib.error.HTTPError as exc:
                assert exc.code == 403
            else:
                raise AssertionError("path traversal was accepted")

            content = base64.b64encode(b"after").decode()
            status, applied = request("http://127.0.0.1:18791/v1/apply", "bridge-test-token", "POST", {"files": [{"path": "agent/chat_server.py", "content_b64": content}]})
            assert status == 200
            assert applied["after"]["agent/chat_server.py"]
            assert (root / "agent" / "chat_server.py").read_text() == "after"

            status, rolled = request("http://127.0.0.1:18791/v1/rollback", "bridge-test-token", "POST", {"receipt_id": applied["receipt_id"]})
            assert status == 200
            assert (root / "agent" / "chat_server.py").read_text() == "before"
        finally:
            process.terminate()
            process.wait(timeout=5)
    print("DURABLE_BRIDGE_SMOKE_OK")


if __name__ == "__main__":
    main()
