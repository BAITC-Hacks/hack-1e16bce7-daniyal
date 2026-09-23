import asyncio
from dataclasses import replace
import json

import httpx
import pytest

from app.application.explanation_facts import explanation_facts
from app.domain.models import ExplanationContext, RankedRecommendation
from app.infrastructure.explanations import ExplanationSettings, OllamaExplanationProvider, explanation_provider


@pytest.fixture
def context():
    rec = RankedRecommendation("EV_010", .8, "Senior", {"design": 2}, {"design": 1},
        ("closes_target_grade_gap",), "Middle", {"design": 2}, {"design": 4}, {"no_show": 3}, 50, 75)
    return ExplanationContext("ru", (rec,), {"design": "System Design"})


def invoke(context, handler, **overrides):
    async def run():
        settings = ExplanationSettings(_env_file=None, llm_provider="ollama", openai_api_key="", **overrides)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await OllamaExplanationProvider(settings, client=client).explain_with_metadata(context)
    return asyncio.run(run())


def plan(context):
    return {"explanations": [{"event_id": key, "segments": [
        {"fact_id": fact.fact_id, "wording": "supportive"} for fact in facts
    ]} for key, facts in explanation_facts(context).items()]}


@pytest.mark.parametrize("locale", ["ru", "kk", "en"])
def test_local_generation_needs_no_key_and_preserves_facts(context, locale):
    context = replace(context, locale=locale)
    def handler(request):
        body = json.loads(request.content)
        assert request.url.path == "/api/chat"
        assert "authorization" not in request.headers
        assert body["think"] is False and body["stream"] is False
        assert body["format"]["additionalProperties"] is False
        assert json.loads(body["messages"][1]["content"])["locale"] == locale
        assert "employee_id" not in request.content.decode()
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps(plan(context))}})
    result = invoke(context, handler)
    assert result.source == "ollama" and result.fallback_reason is None
    assert "System Design" in result.texts["EV_010"]


@pytest.mark.parametrize("failure", ["invented", "missing", "duplicate", "truncated", "offline", "timeout", "http"])
def test_local_failures_are_explicit_safe_fallbacks(context, failure):
    def handler(request):
        if failure == "offline":
            raise httpx.ConnectError("unavailable", request=request)
        if failure == "timeout":
            raise httpx.ReadTimeout("slow", request=request)
        if failure == "http":
            return httpx.Response(503)
        body = plan(context)
        segments = body["explanations"][0]["segments"]
        if failure == "invented": segments[0]["fact_id"] = "promotion_guaranteed"
        if failure == "missing": segments.pop()
        if failure == "duplicate": segments.append(segments[0])
        return httpx.Response(200, json={"done": True, "done_reason": "length" if failure == "truncated" else "stop",
                                        "message": {"content": json.dumps(body)}})
    result = invoke(context, handler)
    assert result.source == "template" and result.fallback_reason is not None
    assert "System Design" in result.texts["EV_010"]
    assert "promotion_guaranteed" not in result.texts["EV_010"]


def test_disabled_and_empty_do_not_call_model(context):
    def forbidden(request):
        pytest.fail("network must not be called")
    assert invoke(context, forbidden, llm_enabled=False).fallback_reason == "disabled"
    assert invoke(replace(context, recommendations=()), forbidden).fallback_reason == "empty"
    assert isinstance(explanation_provider(ExplanationSettings(_env_file=None, llm_provider="ollama")), OllamaExplanationProvider)
