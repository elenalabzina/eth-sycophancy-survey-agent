"""Offline contract checks for the v0.3 conversational treatment."""
from sycophancy_treatments.policies import load_default_policies
from sycophancy_treatments.survey_agent import SurveyAgent


class FakeModel:
    def complete(self, messages, **kwargs):
        return "A short reply."


def test_v03_shared_constraints_and_distinct_system_prompts():
    p = load_default_policies("configs/v03")
    assert p["neutral"].version == p["sycophantic"].version == "0.3.0"
    assert p["neutral"].shared_constraints == p["sycophantic"].shared_constraints
    assert p["neutral"].system_prompt != p["sycophantic"].system_prompt
    assert "15–35 words" in p["neutral"].system_prompt
    assert "15–35 words" in p["sycophantic"].system_prompt


def test_survey_agent_loads_v03_for_both_arms():
    agent = SurveyAgent(FakeModel())
    for condition in ("neutral", "sycophantic"):
        assert agent.policies[condition].version == "0.3.0"


