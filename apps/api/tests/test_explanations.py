import asyncio
from dataclasses import replace
import json

import httpx
import pytest

from app.application.explanation_facts import explanation_facts
from app.domain.models import ExplanationContext, RankedRecommendation
from app.infrastructure.explanations import ExplanationSettings, OpenAIExplanationProvider, TemplateExplanationProvider


@pytest.fixture
def context():
    rec = RankedRecommendation("EV_010", .8, "Senior", {"design": 2}, {"design": 1},
                               ("closes_target_grade_gap",), "Middle", {"design": 2}, {"design": 4},
                               {"no_show": 3}, 50, 75)
    return ExplanationContext("ru", (rec,), {"design": "System Design"})


def settings(**kwargs):
    return ExplanationSettings(_env_file=None, openai_api_key="fake-test-key", **kwargs)


def plan_for(context):
    return {"explanations": [
        {"event_id": key, "segments": [{"fact_id": fact.fact_id, "wording": "supportive"} for fact in facts]}
        for key, facts in explanation_facts(context).items()
    ]}


def response_body(plan):
    return {"status": "completed", "output": [{"type": "message", "content": [
        {"type": "output_text", "text": json.dumps(plan)}]}]}


def invoke(context, handler, config=None):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await OpenAIExplanationProvider(config or settings(), client=client).explain_with_metadata(context)
    return asyncio.run(run())


@pytest.mark.parametrize("locale,expected", [("ru", "текущий"), ("kk", "Қазіргі"), ("en", "current")])
def test_locales_and_missing_key_never_call_network(context, locale, expected):
    def forbidden(request):
        pytest.fail("must not call OpenAI")
    result = invoke(replace(context, locale=locale), forbidden, ExplanationSettings(_env_file=None, openai_api_key=""))
    assert result.source == "template" and result.fallback_reason == "missing_key"
    assert expected in result.texts["EV_010"]
    assert "System Design" in result.texts["EV_010"]


def test_valid_response_private_payload_and_structured_schema(context):
    def handler(request):
        payload = json.loads(request.content)
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert payload["store"] is False
        assert payload["text"]["format"]["strict"] is True
        assert "employee_id" not in payload["input"] and "full_name" not in payload["input"]
        return httpx.Response(200, json=response_body(plan_for(context)))
    result = invoke(context, handler)
    assert result.source == "openai"
    assert "с 2 до 1" in result.texts["EV_010"]


@pytest.mark.parametrize("mutation", ["event", "duplicate_event", "missing_event", "fact", "missing_fact", "duplicate_fact", "free_text", "score"])
def test_invalid_model_output_falls_back(context, mutation):
    plan = plan_for(context)
    item = plan["explanations"][0]
    if mutation == "event": item["event_id"] = "INVENTED"
    elif mutation == "duplicate_event": plan["explanations"].append(item)
    elif mutation == "missing_event": plan["explanations"] = []
    elif mutation == "fact": item["segments"][0]["fact_id"] = "fiction"
    elif mutation == "missing_fact": item["segments"].pop()
    elif mutation == "duplicate_fact": item["segments"].append(item["segments"][0])
    elif mutation == "free_text": item["segments"][0]["wording"] = "Guaranteed promotion to CEO"
    elif mutation == "score": item["score"] = 999
    result = invoke(context, lambda request: httpx.Response(200, json=response_body(plan)))
    assert result.fallback_reason == "invalid_response"
    assert result.texts == asyncio.run(TemplateExplanationProvider().explain(context))


@pytest.mark.parametrize("status,reason", [(401, "api_error"), (429, "rate_limit"), (500, "api_error")])
def test_api_failures_are_safe(context, status, reason, caplog):
    result = invoke(context, lambda request: httpx.Response(status, text="secret-provider-message"))
    assert result.fallback_reason == reason
    assert "secret-provider-message" not in caplog.text and "fake-test-key" not in caplog.text


@pytest.mark.parametrize("body", [{"status": "incomplete"}, {"status": "completed", "output": []},
                                   {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal"}]}]},
                                   {"status": "completed", "output": None}])
def test_incomplete_refused_and_malformed_responses(context, body):
    assert invoke(context, lambda request: httpx.Response(200, json=body)).source == "template"


def test_timeout_and_transport_errors(context):
    async def slow(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json={})
    assert invoke(context, slow, settings(openai_timeout_seconds=.01)).fallback_reason == "timeout"
    def disconnected(request):
        raise httpx.ConnectError("private", request=request)
    assert invoke(context, disconnected).fallback_reason == "network_error"


def test_disabled_empty_and_invalid_facts(context):
    def forbidden(request):
        pytest.fail("must not request")
    assert invoke(context, forbidden, settings(llm_enabled=False)).fallback_reason == "disabled"
    assert invoke(replace(context, recommendations=()), forbidden).texts == {}
    bad = replace(context.recommendations[0], expected_gains={"design": -1})
    with pytest.raises(ValueError):
        invoke(replace(context, recommendations=(bad,)), forbidden)


def test_provider_restores_original_order(context):
    other = replace(context.recommendations[0], event_id="EV_011")
    context = replace(context, recommendations=(*context.recommendations, other))
    plan = plan_for(context)
    plan["explanations"].reverse()
    result = invoke(context, lambda request: httpx.Response(200, json=response_body(plan)))
    assert list(result.texts) == ["EV_010", "EV_011"]
