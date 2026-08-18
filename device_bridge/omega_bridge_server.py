#!/usr/bin/env python3
"""Omega durable scoped device bridge.

This service is intentionally not a general shell. It supports only approved
Omega workspace operations and fails closed. Creator attribution: Thomas Lee Harvey.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import subprocess
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(os.environ.get("OMEGA_BRIDGE_ROOT", Path.home() / "omega-agent-v2")).resolve()
TOKEN_FILE = Path(os.environ.get("OMEGA_BRIDGE_TOKEN_FILE", ROOT / ".omega-bridge" / "token"))
RECEIPT_DIR = Path(os.environ.get("OMEGA_BRIDGE_RECEIPT_DIR", ROOT / ".omega-bridge" / "receipts"))
PORT = int(os.environ.get("OMEGA_BRIDGE_PORT", "8791"))
MAX_BODY = 25 * 1024 * 1024
LEASE_SECONDS = int(os.environ.get("OMEGA_BRIDGE_LEASE_SECONDS", "1800"))

ALLOWED_FILES = {
    "agent/agent_loop.py",
    "agent/chat_server.py",
    "agent/decision_provenance.py",
    "api/claude_client.py",
    "api/groq_client.py",
    "lib/omega_proof.py",
    "render.yaml",
    "tests/test_claude_adapter.py",
    "tests/test_provider_fallback.py",
    "tests/test_transport_resilience.py",
    "tests/test_vision_payload.py",
}

COMMANDS = {
    "status": ["git", "status", "--short"],
    "syntax": ["python3", "-m", "py_compile", "agent/agent_loop.py", "agent/chat_server.py", "api/claude_client.py", "api/groq_client.py"],
    "regression": ["python3", "tests/test_claude_adapter.py"],
    "restart_sync_service": ["bash", "-lc", '"$HOME/install_omega_sync_service.sh"'],
}


def ensure_runtime():
    TOKEN_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    RECEIPT_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not TOKEN_FILE.exists():
        TOKEN_FILE.write_text(secrets.token_urlsafe(48) + "\n")
        TOKEN_FILE.chmod(0o600)
    if not ROOT.is_dir():
        raise RuntimeError(f"bridge root does not exist: {ROOT}")


def token():
    return TOKEN_FILE.read_text().strip()


def safe_path(relative):
    if not isinstance(relative, str) or relative not in ALLOWED_FILES:
        raise PermissionError("path is outside the approved Omega bridge allowlist")
    candidate = (ROOT / relative).resolve()
    if candidate.parent != (ROOT / relative).parent.resolve() or not str(candidate).startswith(str(ROOT) + os.sep):
        raise PermissionError("path escapes the approved Omega root")
    return candidate


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def receipt(kind, payload):
    receipt_id = f"{int(time.time())}-{secrets.token_hex(8)}"
    data = {"receipt_id": receipt_id, "kind": kind, "created_at": time.time(), **payload}
    target = RECEIPT_DIR / f"{receipt_id}.json"
    fd, temp = tempfile.mkstemp(prefix=".receipt-", dir=RECEIPT_DIR, text=True)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return data


class Handler(BaseHTTPRequestHandler):
    server_version = "OmegaDurableBridge/1.0"

    def log_message(self, fmt, *args):
        print("[omega-bridge] " + fmt % args, flush=True)

    def send_json(self, status, body):
        raw = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def authorized(self):
        value = self.headers.get("Authorization", "")
        return secrets.compare_digest(value, "Bearer " + token())

    def body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > MAX_BODY:
            raise ValueError("request body exceeds bridge limit")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        if urlparse(self.path).path != "/health":
            return self.send_json(404, {"error": "not_found"})
        if not self.authorized():
            return self.send_json(401, {"error": "unauthorized"})
        return self.send_json(200, {
            "status": "ok",
            "service": "omega-durable-bridge",
            "root": str(ROOT),
            "lease_seconds": LEASE_SECONDS,
            "capabilities": sorted(COMMANDS),
            "allowlist_count": len(ALLOWED_FILES),
        })

    def do_POST(self):
        if not self.authorized():
            return self.send_json(401, {"error": "unauthorized"})
        try:
            path = urlparse(self.path).path
            payload = self.body()
            if path == "/v1/read":
                target = safe_path(payload.get("path"))
                data = target.read_bytes()
                if len(data) > 2 * 1024 * 1024:
                    raise ValueError("file exceeds read limit")
                return self.send_json(200, {"path": payload["path"], "sha256": sha256(data), "content_b64": base64.b64encode(data).decode()})
            if path == "/v1/apply":
                return self.apply(payload)
            if path == "/v1/exec":
                return self.execute(payload)
            if path == "/v1/rollback":
                return self.rollback(payload)
            return self.send_json(404, {"error": "not_found"})
        except PermissionError as exc:
            return self.send_json(403, {"error": "forbidden", "message": str(exc)})
        except Exception as exc:
            return self.send_json(400, {"error": "bad_request", "message": str(exc)})

    def apply(self, payload):
        changes = payload.get("files")
        if not isinstance(changes, list) or not changes:
            raise ValueError("files must be a non-empty list")
        before = {}
        after = {}
        decoded = []
        for item in changes:
            rel = item.get("path")
            target = safe_path(rel)
            raw = base64.b64decode(item.get("content_b64", ""), validate=True)
            expected = item.get("sha256")
            if expected and expected != sha256(raw):
                raise ValueError(f"sha256 mismatch for {rel}")
            before[rel] = sha256(target.read_bytes()) if target.exists() else None
            decoded.append((rel, target, raw))
        backups = {}
        try:
            for rel, target, raw in decoded:
                if target.exists():
                    backup = tempfile.NamedTemporaryFile(prefix="omega-backup-", delete=False)
                    backup.write(target.read_bytes())
                    backup.close()
                    backups[rel] = backup.name
                target.parent.mkdir(parents=True, exist_ok=True)
                fd, temp = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent, text=False)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp, target)
                after[rel] = sha256(raw)
        except Exception:
            for rel, target, _ in decoded:
                backup = backups.get(rel)
                if backup and os.path.exists(backup):
                    os.replace(backup, target)
            raise
        result = receipt("apply", {"files": list(before), "before": before, "after": after, "rollback": backups})
        return self.send_json(200, result)

    def execute(self, payload):
        name = payload.get("command")
        if name not in COMMANDS:
            raise PermissionError("command is not in the approved capability registry")
        result = subprocess.run(COMMANDS[name], cwd=ROOT, capture_output=True, text=True, timeout=120)
        data = receipt("exec", {"command": name, "returncode": result.returncode, "stdout": result.stdout[-8000:], "stderr": result.stderr[-8000:]})
        return self.send_json(200 if result.returncode == 0 else 500, data)

    def rollback(self, payload):
        target = RECEIPT_DIR / f"{payload.get('receipt_id')}.json"
        if not target.exists():
            raise ValueError("receipt not found")
        record = json.loads(target.read_text())
        for rel, backup in record.get("rollback", {}).items():
            safe_path(rel)
            if os.path.exists(backup):
                os.replace(backup, ROOT / rel)
        return self.send_json(200, receipt("rollback", {"source_receipt": record["receipt_id"], "files": list(record.get("rollback", {}))}))


if __name__ == "__main__":
    ensure_runtime()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
