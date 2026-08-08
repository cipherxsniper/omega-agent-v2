#!/data/data/com.termux/files/usr/bin/bash
cd ~/omega-agent-v2
FILE=./agent/agent_loop.py

echo "=== full run_agent_task function with line numbers ==="
sed -n '305,382p' "$FILE"

echo ""
echo "=== where message.get('content') or final content is set ==="
grep -n -B2 -A8 "message\[.content.\]\|message.get(.content.\|final.*=.*True\|\"final\": true" "$FILE"

echo ""
echo "=== SYSTEM_PROMPT definition (may be in another file) ==="
grep -rn "SYSTEM_PROMPT\s*=" ~/omega-agent-v2/agent/ 2>/dev/null | head -5
