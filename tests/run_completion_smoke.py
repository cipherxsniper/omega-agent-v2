import os
import queue
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from agent import chat_server


def run_failure_case():
    job_id = "smoke-failure"
    chat_server._jobs[job_id] = {"status": "queued", "message": "test", "max_steps": 1, "step_queue": queue.Queue()}
    original = chat_server.run_agent_task
    try:
        def fail(*args, **kwargs):
            raise RuntimeError("synthetic failure")
        chat_server.run_agent_task = fail
        chat_server._run_job(job_id, "test", 1)
        job = chat_server._jobs[job_id]
        assert job["status"] == "failed"
        assert "synthetic failure" in job["response"]
        assert job["step_queue"].get_nowait() is None
    finally:
        chat_server.run_agent_task = original
        del chat_server._jobs[job_id]


def run_success_case():
    job_id = "smoke-success"
    chat_server._jobs[job_id] = {"status": "queued", "message": "test", "max_steps": 1, "step_queue": queue.Queue()}
    original = chat_server.run_agent_task
    try:
        def succeed(*args, **kwargs):
            final = {"step": 0, "role": "assistant", "content": "OK", "final": True}
            kwargs["on_step"](final)
            return [final]
        chat_server.run_agent_task = succeed
        chat_server._run_job(job_id, "test", 1)
        job = chat_server._jobs[job_id]
        assert job["status"] == "done"
        assert job["response"] == "OK"
        assert job["step_queue"].get_nowait()["final"] is True
        assert job["step_queue"].get_nowait() is None
    finally:
        chat_server.run_agent_task = original
        del chat_server._jobs[job_id]


if __name__ == "__main__":
    run_failure_case()
    run_success_case()
    print("COMPLETION_CONTRACT_SMOKE_OK")
