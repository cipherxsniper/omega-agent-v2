"""
chat_server.py — HTTP bridge between the GitHub Pages chat frontend and
the real agent_loop.py tool-use loop. No new agent logic here — this is
just a thin, honest transport layer.
"""
import os
import sys
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import Flask, request, jsonify
from flask_cors import CORS

from agent.agent_loop import run_agent_task

logger = logging.getLogger("OmegaChatServer")
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# Restrict CORS to your actual GitHub Pages origin — replace before deploying.
ALLOWED_ORIGIN = os.getenv("OMEGA_ALLOWED_ORIGIN", "https://YOUR-USERNAME.github.io")
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGIN}})

LOG_PATH = os.path.expanduser("~/.omega/logs/agent_loop_signed.log")


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json(silent=True) or {}
    message = body.get("message", "").strip()
    max_steps = int(body.get("max_steps", 10))

    if not message:
        return jsonify({"error": "Missing 'message' in request body"}), 400

    try:
        transcript = run_agent_task(
            message,
            max_steps=max_steps,
            signed_log=LOG_PATH,
            cwd_hint=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        )
    except Exception as e:
        logger.error(f"Agent task failed: {e}", exc_info=True)
        return jsonify({"error": f"Agent execution failed: {e}"}), 500

    final_entry = next((e for e in reversed(transcript) if e.get("final")), None)
    final_text = final_entry["content"] if final_entry else "(no final response — see transcript)"

    return jsonify({
        "response": final_text,
        "transcript": transcript,
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8420))
    app.run(host="0.0.0.0", port=port)
