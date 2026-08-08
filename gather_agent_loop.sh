#!/data/data/com.termux/files/usr/bin/bash
cd ~/omega-agent-v2
FILE=$(find . -iname "agent_loop.py" | head -1)
echo "=== file: $FILE ==="

echo ""
echo "=== history append points ==="
grep -n -B2 -A8 "messages.append\|history.append" "$FILE"

echo ""
echo "=== chat_completion call sites ==="
grep -n -B2 -A8 "chat_completion(" "$FILE"

echo ""
echo "=== tool result handling ==="
grep -n -B2 -A10 "role.*tool\|tool_result\|\"role\": \"tool\"" "$FILE"

echo ""
echo "=== main loop structure ==="
grep -n "def \|for step\|while " "$FILE"
