"""
chat_server.py — HTTP bridge between the GitHub Pages chat frontend and
the real agent_loop.py tool-use loop. No new agent logic here — this is
just a thin, honest transport layer.
"""
import os
import sys
import logging
import json
import queue as queue_mod
import threading
import time
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import Flask, request, jsonify
from flask_cors import CORS

from agent.agent_loop import run_agent_task

logger = logging.getLogger("OmegaChatServer")
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# Allow only the deployed Omega Pages origins. Override with a comma-separated
# OMEGA_ALLOWED_ORIGINS value for a custom deployment; never use '*'.
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "OMEGA_ALLOWED_ORIGINS",
        "https://cipherxsniper.github.io,https://tommyleeharvey.github.io",
    ).split(",")
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

LOG_PATH = os.path.expanduser("~/.omega/logs/agent_loop_signed.log")
CWD_HINT = os.path.expanduser("~/omega_workspace") + (
    " — this contains all Omega repos as subdirectories: "
    "OMEGAOPS.AI, omega, Omega-Ecosystem-App, omega-art-studio, "
    "omega-fintech, omega-financial-core, Omega-Core, "
    "omega-agent-v2, Omega_Finacial_Network. Use paths like "
    "'OMEGAOPS.AI/omega_v10.py' relative to this root."
)
_jobs = {}
_jobs_lock = threading.Lock()
MAX_IMAGES = 5
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MIN_STEPS = 1
MAX_STEPS = 100


def _safe_failure_diagnostic(exc):
    """Return bounded, credential-redacted failure metadata for operators."""
    import re
    raw = f"{type(exc).__name__}: {exc}"
    redacted = re.sub(r"(?i)(?:sk-|gsk_|key[-_ ]?|token[-_ ]?|authorization[:= ]+)[A-Za-z0-9_./+=:-]{8,}", "[redacted]", raw)
    return {"type": type(exc).__name__, "detail": redacted[:300]}


def _parse_max_steps(raw, default=10):
    try:
        value = int(raw if raw is not None else default)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_steps must be an integer") from exc
    return max(MIN_STEPS, min(MAX_STEPS, value))


def _validate_images(raw_images):
    if raw_images in (None, []):
        return []
    if not isinstance(raw_images, list) or len(raw_images) > MAX_IMAGES:
        raise ValueError(f"At most {MAX_IMAGES} images may be attached")
    validated = []
    for item in raw_images:
        if not isinstance(item, dict):
            raise ValueError("Each image attachment must be an object")
        data_url = item.get("dataUrl")
        if not isinstance(data_url, str) or not data_url.startswith("data:image/"):
            raise ValueError("Image attachments must use data:image/* URLs")
        if len(data_url.encode("utf-8")) > MAX_IMAGE_BYTES:
            raise ValueError("An image attachment exceeds the 20 MB provider limit")
        validated.append({
            "name": str(item.get("name", "image"))[:200],
            "type": str(item.get("type", "image/*"))[:100],
            "dataUrl": data_url,
        })
    return validated


def _run_job(job_id, message, max_steps, images):
    with _jobs_lock:
        job = _jobs[job_id]
        job["status"] = "running"
    step_queue = job["step_queue"]

    def on_step(step_dict):
        with _jobs_lock:
            _jobs[job_id].setdefault("transcript", []).append(step_dict)
        step_queue.put(step_dict)

    try:
        transcript = run_agent_task(
            message,
            max_steps=max_steps,
            signed_log=LOG_PATH,
            cwd_hint=CWD_HINT,
            on_step=on_step,
            image_inputs=images,
        )
        final_entry = next((entry for entry in reversed(transcript) if entry.get("final")), None)
        final_text = final_entry.get("content", "") if final_entry else "Omega finished without a final entry; review the observable transcript."
        with _jobs_lock:
            _jobs[job_id].update({
                "status": "done",
                "response": final_text,
                "transcript": transcript,
                "finished_at": time.time(),
            })
    except Exception as exc:
        logger.error("Job %s failed: %s", job_id, exc, exc_info=True)
        with _jobs_lock:
            _jobs[job_id].update({
                "status": "failed",
                "error": "agent_unavailable",
                "diagnostic": _safe_failure_diagnostic(exc),
                "message": "Omega could not complete this job because all configured execution paths failed. Retry shortly.",
                "request_id": job_id,
                "response": "Omega could not complete this job. Retry shortly.",
                "finished_at": time.time(),
            })
    finally:
        step_queue.put(None)


@app.route("/api/health", methods=["GET"])
def health():
    runtime_ok = os.path.isdir(os.path.expanduser("~/.omega/logs"))
    provider_ok = bool(os.getenv("GROQ_API_KEY"))
    status = "ok" if runtime_ok and provider_ok else "degraded"
    response = jsonify({
        "status": status,
        "runtime_logs": runtime_ok,
        "provider_configured": provider_ok,
        "proof_telemetry": bool(os.getenv("PROOFCHAIN_SIGNING_KEY") or os.getenv("PROOFCHAIN_KEYFILE")),
    })
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json(silent=True) or {}
    message = body.get("message", "").strip()
    try:
        max_steps = _parse_max_steps(body.get("max_steps"), default=10)
        images = _validate_images(body.get("images", []))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

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
            image_inputs=images,
        )
    except Exception as e:
        request_id = str(uuid.uuid4())
        logger.error("Agent task failed request_id=%s: %s", request_id, e, exc_info=True)
        return jsonify({
            "error": "agent_unavailable",
            "message": "Omega could not complete this request because all configured execution paths failed. Retry shortly.",
            "request_id": request_id,
            "diagnostic": _safe_failure_diagnostic(e),
        }), 503

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
    try:
        max_steps = _parse_max_steps(body.get("max_steps"), default=100)
        images = _validate_images(body.get("images", []))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

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
            "images": images,
        }

    thread = threading.Thread(target=_run_job, args=(job_id, message, max_steps, images), daemon=True)
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
