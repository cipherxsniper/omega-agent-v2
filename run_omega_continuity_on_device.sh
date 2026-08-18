#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${OMEGA_ROOT:-$HOME/omega-agent-v2}"
REMOTE_NAME="cipherxsniper"
REMOTE_URL="https://github.com/cipherxsniper/omega-agent-v2.git"
BACKUP_ROOT="$HOME/omega-local-backups"
STAMP="$(date +%Y%m%d%H%M%S)"
BACKUP="$BACKUP_ROOT/continuity-$STAMP"

for command_name in git python3 sha256sum; do
  command -v "$command_name" >/dev/null 2>&1 || { echo "Missing required command: $command_name" >&2; exit 1; }
done
[ -d "$ROOT/.git" ] || { echo "Omega checkout not found: $ROOT" >&2; exit 1; }
mkdir -p "$BACKUP"
cd "$ROOT"

git status --short > "$BACKUP/status.txt" || true
git diff > "$BACKUP/working-tree.patch" || true
git diff --cached > "$BACKUP/index.patch" || true
[ -f device_bridge/omega_bridge_server.py ] && cp -p device_bridge/omega_bridge_server.py "$BACKUP/omega_bridge_server.py" || true

if git remote get-url "$REMOTE_NAME" >/dev/null 2>&1; then
  git remote set-url "$REMOTE_NAME" "$REMOTE_URL"
else
  git remote add "$REMOTE_NAME" "$REMOTE_URL"
fi

git fetch --quiet "$REMOTE_NAME" main
REMOTE_HEAD="$(git rev-parse "$REMOTE_NAME/main")"
git checkout -B main "$REMOTE_HEAD"
git reset --hard "$REMOTE_HEAD"

for file in tools/omega_continuity.py tools/omega_reliability_audit.py agent/shadow_council.py agent/replay_lab.py agent/mission_autopilot.py agent/agent_loop.py tests/test_continuity.py tests/test_reliability_audit.py tests/test_shadow_council.py tests/test_replay_lab.py tests/test_mission_autopilot.py; do
  [ -f "$file" ] || { echo "Required file missing: $file" >&2; exit 1; }
done

PYTHONPATH=. python3 -m py_compile tools/omega_continuity.py tools/omega_reliability_audit.py agent/shadow_council.py agent/replay_lab.py agent/mission_autopilot.py agent/agent_loop.py
PYTHONPATH=. python3 tests/test_continuity.py
PYTHONPATH=. python3 tests/test_reliability_audit.py
PYTHONPATH=. python3 tests/test_shadow_council.py
PYTHONPATH=. python3 tests/test_replay_lab.py
PYTHONPATH=. python3 tests/test_mission_autopilot.py

PYTHONPATH=. python3 tools/omega_continuity.py --generate --manifest omega_continuity_manifest.json --receipt omega_continuity_receipt.json
STATUS="$(python3 -c 'import json; print(json.load(open("omega_continuity_receipt.json"))["status"])')"
[ "$STATUS" = "verified" ] || { echo "CONTINUITY_FAILED_CLOSED status=$STATUS" >&2; exit 1; }

printf 'OMEGA_CONTINUITY_VERIFIED\n'
printf 'REMOTE_HEAD=%s\n' "$REMOTE_HEAD"
printf 'BACKUP=%s\n' "$BACKUP"
printf 'RECEIPT=%s\n' "$ROOT/omega_continuity_receipt.json"
printf 'MANIFEST=%s\n' "$ROOT/omega_continuity_manifest.json"
