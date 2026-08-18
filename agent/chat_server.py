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
            cwd_hint=os.path.expanduser("~/omega_workspace") + (
                " — this contains all Omega repos as subdirectories: "
                "OMEGAOPS.AI, omega, Omega-Ecosystem-App, omega-art-studio, "
                "omega-fintech, omega-financial-core, Omega-Core, "
                "omega-agent-v2, Omega_Finacial_Network. Use paths like "
                "'OMEGAOPS.AI/omega_v10.py' relative to this root."
            ),
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


@app.route("/api/job/start", methods=["POST"])
def job_start():
    """Background path - for long autonomous tasks. Returns immediately
    with a job_id instead of blocking; poll /api/job/<id> for status.
    require_plan is forced on here, since long-running tasks are exactly
    where a durable plan matters most."""
    body = request.get_json(silent=True) or {}
    message = body.get("message", "").strip()
    max_steps = int(body.get("max_steps", 100))

    if not message:
        return jsonify({"error": "Missing 'message' in request body"}), 400

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "queued",
            "message": message,
            "max_steps": max_steps,
            "started_at": time.time(),
            "step_queue": queue_mod.Queue(),
        }

    thread = threading.Thread(target=_run_job, args=(job_id, message, max_steps), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id, "status": "queued"})


@app.route("/api/job/<job_id>", methods=["GET"])
def job_status(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": f"No job found with id {job_id}"}), 404
    safe_job = {k: v for k, v in job.items() if k != "step_queue"}
    return jsonify({"job_id": job_id, **safe_job})


@app.route("/api/job/stream/<job_id>", methods=["GET"])
def job_stream(job_id):
    """
    Server-Sent Events stream of live transcript steps for a running
    job. One-directional, no new dependencies (SSE is plain HTTP with
    a specific content-type + chunked text/event-stream format), and
    works cleanly through both Render and Cloudflare tunnels.

    Each event's data payload is one transcript step as JSON. A final
    event with data: {"done": true} signals stream end - the frontend
    should close its EventSource on seeing this rather than relying on
    the connection dropping.
    """
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": f"No job found with id {job_id}"}), 404

    step_queue = job["step_queue"]

    def generate():
        # Replay any steps that already happened before this stream
        # connected (e.g. client reconnecting mid-job), then continue
        # live from the queue.
        with _jobs_lock:
            already = list(job.get("transcript", []))

        def step_key(step):
            """Stable identity for replay de-duplication across SSE reconnects."""
            if not isinstance(step, dict):
                return None
            if step.get("role") == "tool" and step.get("tool_call_id"):
                return ("tool", step["tool_call_id"])
            return (step.get("role"), step.get("step"), json.dumps(step.get("tool_calls"), sort_keys=True, default=str))

        seen = set()
        for step in already:
            key = step_key(step)
            if key is not None:
                seen.add(key)
            yield f"data: {json.dumps(step)}\n\n"

        while True:
            try:
                step = step_queue.get(timeout=30)
            except queue_mod.Empty:
                # Heartbeat comment, keeps proxies/tunnels from closing
                # an idle connection.
                yield ": heartbeat\n\n"
                continue
            if step is None:
                with _jobs_lock:
                    completion = {
                        "done": True,
                        "status": job.get("status"),
                        "response": job.get("response"),
                        "error": job.get("error"),
                    }
                yield f"data: {json.dumps(completion)}\n\n"
                break
            key = step_key(step)
            if key is not None and key in seen:
                continue
            if key is not None:
                seen.add(key)
            yield f"data: {json.dumps(step)}\n\n"

    return app.response_class(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # disable nginx buffering if present
    })


@app.route("/api/job", methods=["GET"])
def job_list():
    """List all known jobs (in-memory, this process's lifetime only)."""
    with _jobs_lock:
        summary = {
            jid: {"status": j["status"], "message": j["message"][:100], "started_at": j["started_at"]}
            for jid, j in _jobs.items()
        }
    return jsonify(summary)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8420))
    app.run(host="0.0.0.0", port=port)
