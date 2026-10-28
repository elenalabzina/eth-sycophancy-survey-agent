from sycophancy_treatments.survey_agent import SurveyAgent, normalize_query


class FakeModel:
    def __init__(self):
        self.calls=[]
    def complete(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if kwargs.get("max_tokens")==80:
            return "QUERY: wind power grid balancing evidence"
        return "Evidence is mixed; consider the tradeoffs."


def test_both_conditions_use_identical_runtime_and_web():
    m=FakeModel()
    seen=[]
    a=SurveyAgent(m,search=lambda q:(seen.append(q) or [{"title":"Energy study","url":"https://example.org","content":"Some evidence."}]))
    s1=a.start("neutral", internet_access=True)
    s2=a.start("sycophantic", internet_access=True)
    assert a.reply(s1,"What is the latest evidence?")["turn"]==1
    assert a.reply(s2,"What is the latest evidence?")["turn"]==1
    assert seen==["wind power grid balancing evidence"]*2
    p1=m.calls[1][0]
    p2=m.calls[3][0]
    assert p1[-1]==p2[-1]
    assert "Shared survey constraints" in p1[0]["content"]
    assert "Shared survey constraints" in p2[0]["content"]
    assert p1[0]["content"]!=p2[0]["content"]


def test_session_remains_in_same_condition():
    a=SurveyAgent(FakeModel())
    sid=a.start("neutral")
    a.reply(sid,"First question")
    a.reply(sid,"Second question")
    assert a.sessions[sid].condition=="neutral"
    assert len(a.sessions[sid].messages)==4


def test_basic_search_query_privacy_guard():
    assert normalize_query("solar generation costs")=="solar generation costs"
    import pytest
    for value in ("me@example.com","my address is central","https://private.example"):
        with pytest.raises(ValueError):
            normalize_query(value)


def test_invalid_condition_rejected():
    import pytest
    with pytest.raises(ValueError):
        SurveyAgent(FakeModel()).start("unknown")


def test_fast_chat_skips_search_planner():
    from sycophancy_treatments.survey_agent import needs_current_search
    assert not needs_current_search("I disagree with your assessment. Why?")
    assert needs_current_search("Check recent sources on European AI regulation")
    m=FakeModel()
    a=SurveyAgent(m,search=lambda q: (_ for _ in ()).throw(AssertionError("unexpected search")))
    a.reply(a.start("neutral"),"I disagree with your assessment. Why?")
    assert len(m.calls)==1
