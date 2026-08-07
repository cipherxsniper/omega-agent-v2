import os
import sys
import json
import base64
import hashlib
from pathlib import Path
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey
)
from cryptography.exceptions import InvalidSignature


def _load_signer():
    b64key = os.environ.get("PROOFCHAIN_SIGNING_KEY")
    if b64key:
        raw = base64.b64decode(b64key)[:32]
    else:
        keyfile = os.environ.get("PROOFCHAIN_KEYFILE")
        if not keyfile:
            raise RuntimeError("Neither PROOFCHAIN_SIGNING_KEY nor PROOFCHAIN_KEYFILE set — no placeholder key will be used.")
        data = json.loads(Path(keyfile).expanduser().read_text())
        raw = bytes(data["secret"][:32]) if isinstance(data, dict) else bytes(data[:32])
    priv = Ed25519PrivateKey.from_private_bytes(raw)
    return priv, priv.public_key()


def _prev_hash(log_path: Path) -> str:
    if log_path.exists() and log_path.stat().st_size > 0:
        last_line = log_path.read_text().strip().splitlines()[-1]
        return json.loads(last_line)["entry_hash"]
    return "genesis"


def sign_event(log_path, event_type: str, data: dict) -> dict:
    priv, _ = _load_signer()
    log_path = Path(log_path).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "type": event_type,
        "data": data,
        "prev_hash": _prev_hash(log_path),
        "signed_at": datetime.now(timezone.utc).isoformat(),
    }
    msg = json.dumps(entry, sort_keys=True, default=str).encode()
    sig = base64.b64encode(priv.sign(msg)).decode()
    entry_hash = hashlib.sha256(msg + sig.encode()).hexdigest()
    entry["signature"] = sig
    entry["entry_hash"] = entry_hash

    with open(log_path, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")

    return entry


def verify_log(log_path, pubkey_bytes: bytes = None):
    log_path = Path(log_path).expanduser()
    if not log_path.exists():
        return False, "log does not exist"

    if pubkey_bytes is None:
        _, pub = _load_signer()
    else:
        pub = Ed25519PublicKey.from_public_bytes(pubkey_bytes)

    lines = log_path.read_text().strip().splitlines()
    if not lines:
        return False, "log is empty"

    expected_prev = "genesis"
    for i, line in enumerate(lines):
        entry = json.loads(line)

        if entry.get("prev_hash") != expected_prev:
            return False, f"chain broken at entry {i}: prev_hash mismatch"

        sig_b64 = entry["signature"]
        entry_hash = entry["entry_hash"]
        check_entry = {k: v for k, v in entry.items() if k not in ("signature", "entry_hash")}
        msg = json.dumps(check_entry, sort_keys=True, default=str).encode()

        recomputed_hash = hashlib.sha256(msg + sig_b64.encode()).hexdigest()
        if recomputed_hash != entry_hash:
            return False, f"entry_hash mismatch at entry {i} — log tampered"

        try:
            pub.verify(base64.b64decode(sig_b64), msg)
        except InvalidSignature:
            return False, f"invalid signature at entry {i} — forged or corrupted"

        expected_prev = entry_hash

    return True, f"{len(lines)} entries verified, chain intact"


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "verify":
        ok, msg = verify_log(sys.argv[2])
        print(("OK: " if ok else "FAIL: ") + msg)
        sys.exit(0 if ok else 1)
    else:
        print("usage: python omega_proof.py verify <logfile>")
