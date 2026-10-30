"""Offline checks of the grading dataset shape; no Qwen or Cloudflare required."""
import importlib.util
from pathlib import Path

def module():
    path = Path(__file__).resolve().parents[1] / "scripts/generate_grading_dialogues.py"
    spec = importlib.util.spec_from_file_location("grading_generator", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class StubModel:
    class config:
        model = "fake-model"
    def complete(self, messages, *, max_tokens=None):
        assert messages
        return "I believe this policy deserves a closer look."

def test_100_balanced_three_user_two_assistant_turns(monkeypatch):
    m = module()
    class StubAgent:
        def __init__(self, model):
            pass
        def start(self, condition, topic, duration_seconds=None):
            return (condition, topic)
        def reply(self, session, user_text):
            return {"reply": "That's worth weighing against the trade-offs."}
    monkeypatch.setattr(m, "SurveyAgent", StubAgent)
    items = m.generate(StubModel(), 100)
    assert len(items) == len({item["id"] for item in items}) == 100
    assert sum(x["condition"] == "neutral" for x in items) == 50
    assert sum(x["condition"] == "sycophantic" for x in items) == 50
    assert sum(x["topic"] == "ai" for x in items) == 50
    assert sum(x["topic"] == "energy" for x in items) == 50
    assert all([m["role"] for m in x["messages"]] ==
               ["user","assistant","user","assistant","user"] for x in items)
