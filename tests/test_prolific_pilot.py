"""Offline HTTP tests for the local four-person pilot (no Qwen or Tunnel needed)."""
import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_prolific_pilot.py"
    spec = importlib.util.spec_from_file_location("prolific_pilot_server", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StubModel:
    pass


class StubAgent:
    def __init__(self, *args, **kwargs):
        self.sessions = {}

    def reply(self, session_id, user_text):
        return {"reply": "There are several trade-offs here. Which matters most to you?"}


def test_four_balanced_slots_and_blinded_persistent_conversations(tmp_path, monkeypatch):
    m = load_module()
    monkeypatch.setattr(m, "DB_PATH", tmp_path / "pilot.sqlite")
    monkeypatch.setattr(m, "ChatModel", lambda cfg: StubModel())
    monkeypatch.setattr(m.ModelConfig, "from_yaml", lambda path: None)
    monkeypatch.setattr(m, "SurveyAgent", StubAgent)

    with TestClient(m.app) as client:
        sessions = []
        for n in range(4):
            response = client.post("/api/start", json={
                "prolific_pid": f"TEST{n:03d}", "consent": True,
                "study_id": "STUDY_A", "prolific_session_id": f"SESSION{n}"
            })
            assert response.status_code == 200
            sessions.append(response.json())

        assert all("condition" not in s and "policy" not in s for s in sessions)
        assert all(len(s["messages"]) == 1 for s in sessions)
        assert client.post("/api/start", json={"prolific_pid": "TEST005", "consent": True}).status_code == 403
        assert client.post("/api/start", json={"prolific_pid": "TEST000", "consent": True}).status_code == 409
        assert client.post("/api/start", json={"prolific_pid": "NO_CONSENT", "consent": False}).status_code == 400
        assert client.get("/docs").status_code == 404

        with m.database() as db:
            conditions = [row[0] for row in db.execute("SELECT condition FROM participants")]
        assert conditions.count("neutral") == conditions.count("sycophantic") == 2

        token = sessions[0]["token"]
        response = client.post("/api/message", json={"token": token, "text": "Reliability is essential"})
        assert response.status_code == 200
        assert len(response.json()["messages"]) == 3
        assert "condition" not in response.json()
        state = client.post("/api/state", json={"token": token})
        assert state.status_code == 200
        assert state.json()["messages"] == response.json()["messages"]
        assert client.post("/api/state", json={"token": "fake"}).status_code == 401

        done = client.post("/api/finish", json={"token": token})
        assert done.status_code == 200 and done.json()["finished"] is True
        assert client.post("/api/message", json={"token": token, "text": "again"}).status_code == 409

        with m.database() as db:
            row = db.execute("SELECT * FROM participants WHERE token=?", (token,)).fetchone()
        assert row["finished_at"] is not None
        assert len(json.loads(row["messages_json"])) == 2
        assert row["prolific_pid"] == "TEST000"
