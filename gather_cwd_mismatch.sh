#!/data/data/com.termux/files/usr/bin/bash
cd ~/omega-agent-v2

echo "=== run_bash tool implementation ==="
grep -rn -B3 -A20 "def.*run_bash\|\"run_bash\"\|'run_bash'" agent/ api/ 2>/dev/null | head -80

echo ""
echo "=== list_dir tool implementation (for comparison) ==="
grep -rn -B3 -A20 "def.*list_dir\|\"list_dir\"\|'list_dir'" agent/ api/ 2>/dev/null | head -60

echo ""
echo "=== where workspace root / cwd is defined ==="
grep -rn "workspace_root\|WORKSPACE_ROOT\|cwd=" agent/ api/ 2>/dev/null | head -30
