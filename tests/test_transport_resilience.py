import os
import time

os.environ.setdefault("GROQ_API_KEY", "test-only-provider-key")

from agent import chat_server


def main():
    client = chat_server.app.test_client()

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.get_json()["provider_configured"] is True

    invalid_steps = client.post("/api/chat", json={"message": "test", "max_steps": "bad"})
    assert invalid_steps.status_code == 400
    assert "max_steps" in invalid_steps.get_json()["error"]

    invalid_image = client.post("/api/chat", json={
        "message": "describe",
        "images": [{"dataUrl": "not-an-image"}],
    })
    assert invalid_image.status_code == 400

    original = chat_server.run_agent_task

    def fail(*args, **kwargs):
        raise RuntimeError("simulated provider/runtime failure")

    chat_server.run_agent_task = fail
    try:
        failed = client.post("/api/chat", json={"message": "test"})
        assert failed.status_code == 503
        body = failed.get_json()
        assert body["error"] == "agent_unavailable"
        assert body["request_id"]
        assert body["diagnostic"]["type"] == "RuntimeError"
        assert "secret" not in failed.get_data(as_text=True).lower()

        started = client.post("/api/job/start", json={"message": "test"})
        assert started.status_code == 200
        job_id = started.get_json()["job_id"]
        for _ in range(20):
            status = client.get(f"/api/job/{job_id}").get_json()
            if status.get("status") == "failed":
                break
            time.sleep(0.01)
        assert status["status"] == "failed"
        assert status["error"] == "agent_unavailable"
        assert status["request_id"] == job_id
        assert status["diagnostic"]["type"] == "RuntimeError"
        assert "secret" not in str(status).lower()
    finally:
        chat_server.run_agent_task = original

    print("TRANSPORT_RESILIENCE_SMOKE_OK")


if __name__ == "__main__":
    main()
