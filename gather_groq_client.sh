#!/data/data/com.termux/files/usr/bin/bash
# run from ~/omega-agent-v2
set -e

echo "=== model tier list ==="
grep -n -B2 -A15 -iE "MODEL_TIER|FALLBACK|TIERS\s*=" api/groq_client.py

echo ""
echo "=== reasoning param handling ==="
grep -n -B3 -A10 -i "reasoning" api/groq_client.py

echo ""
echo "=== function that builds the request payload ==="
grep -n -B2 -A20 "def.*chat\|def.*call\|def.*complete" api/groq_client.py | head -100
