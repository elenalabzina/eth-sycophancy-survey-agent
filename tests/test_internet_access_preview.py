"""Internet access is opt-in per session, with search availability validated."""
import pytest

from sycophancy_treatments.survey_agent import SurveyAgent


class StubModel:
    def complete(self, messages, **kwargs):
        return "OK."


def test_internet_off_by_default_even_when_search_available():
    calls = []
    agent = SurveyAgent(StubModel(), search=lambda q: calls.append(q) or [])
    sid = agent.start(topic="ai")
    assert agent.sessions[sid].internet_access is False
    assert agent.transcript(sid)["internet_access"] is False
    agent.reply(sid, "What are the latest AI regulation updates today?")
    assert calls == []


def test_enabling_internet_requires_configured_search():
    agent = SurveyAgent(StubModel(), search=None)
    with pytest.raises(ValueError, match="unavailable"):
        agent.start(internet_access=True)


def test_enabling_internet_is_per_session():
    agent = SurveyAgent(StubModel(), search=lambda q: [])
    sid_on = agent.start(internet_access=True)
    sid_off = agent.start(internet_access=False)
    assert agent.transcript(sid_on)["internet_access"] is True
    assert agent.transcript(sid_off)["internet_access"] is False
