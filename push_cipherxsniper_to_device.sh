#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${OMEGA_ROOT:-$HOME/omega-agent-v2}"
REMOTE_NAME="cipherxsniper"
REMOTE_URL="https://github.com/cipherxsniper/omega-agent-v2.git"
EXPECTED_COMMIT="37dab69dd6cf886c14bd7e9ee7a59c5d831bd55d"
BACKUP_ROOT="$HOME/omega-local-backups"
STAMP="$(date +%Y%m%d%H%M%S)"
BACKUP="$BACKUP_ROOT/$STAMP"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }; }
need git
need python3
need sha256sum

[ -d "$ROOT/.git" ] || { echo "Omega checkout not found: $ROOT" >&2; exit 1; }
mkdir -p "$BACKUP"
cd "$ROOT"

git status --short > "$BACKUP/status.txt" || true
git diff > "$BACKUP/working-tree.patch" || true
git diff --cached > "$BACKUP/index.patch" || true
if [ -f device_bridge/omega_bridge_server.py ]; then
  cp -p device_bridge/omega_bridge_server.py "$BACKUP/omega_bridge_server.py"
fi

if git remote get-url "$REMOTE_NAME" >/dev/null 2>&1; then
  CURRENT_URL="$(git remote get-url "$REMOTE_NAME")"
  [ "$CURRENT_URL" = "$REMOTE_URL" ] || git remote set-url "$REMOTE_NAME" "$REMOTE_URL"
else
  git remote add "$REMOTE_NAME" "$REMOTE_URL"
fi

git fetch --quiet "$REMOTE_NAME" main
REMOTE_HEAD="$(git rev-parse "$REMOTE_NAME/main")"
git cat-file -e "$EXPECTED_COMMIT^{commit}" || { echo "Pinned source commit is unavailable: $EXPECTED_COMMIT" >&2; exit 1; }
git merge-base --is-ancestor "$EXPECTED_COMMIT" "$REMOTE_HEAD" || { echo "Remote does not contain the pinned source commit" >&2; exit 1; }

git checkout -B main "$EXPECTED_COMMIT"
git reset --hard "$EXPECTED_COMMIT"

for file in tools/omega_reliability_audit.py agent/shadow_council.py agent/replay_lab.py agent/agent_loop.py tests/test_reliability_audit.py tests/test_shadow_council.py tests/test_replay_lab.py; do
  [ -f "$file" ] || { echo "Required file missing after sync: $file" >&2; exit 1; }
done

EXPECTED_AUDIT_SHA="9851be56e460b36ceca7ab6b57ad030a180c29b579142aca4c35525e0d05855d"
ACTUAL_AUDIT_SHA="$(sha256sum tools/omega_reliability_audit.py | awk '{print $1}')"
[ "$ACTUAL_AUDIT_SHA" = "$EXPECTED_AUDIT_SHA" ] || { echo "Auditor hash mismatch: $ACTUAL_AUDIT_SHA" >&2; exit 1; }

PYTHONPATH=. python3 -m py_compile tools/omega_reliability_audit.py agent/shadow_council.py agent/replay_lab.py agent/agent_loop.py
PYTHONPATH=. python3 tests/test_reliability_audit.py
PYTHONPATH=. python3 tests/test_shadow_council.py
PYTHONPATH=. python3 tests/test_replay_lab.py

printf 'OMEGA_DEVICE_DELIVERY_VERIFIED\n'
printf 'COMMIT=%s\n' "$(git rev-parse HEAD)"
printf 'AUDITOR_SHA256=%s\n' "$ACTUAL_AUDIT_SHA"
printf 'LOCAL_BACKUP=%s\n' "$BACKUP"
printf 'REMOTE_HEAD=%s\n' "$REMOTE_HEAD"
printf 'REMOTE=%s\n' "$(git remote get-url "$REMOTE_NAME")"
