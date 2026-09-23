"""Integration entry point; callers retain responsibility for DB access and authorization."""
from dataclasses import dataclass

from app.application.ports import ExplanationProvider, RecommendationEngine
from app.domain.models import ExplanationContext, RankedRecommendation, RecommendationContext


@dataclass(frozen=True)
class ExplainedRecommendation:
    facts: RankedRecommendation
    explanation: str


class RecommendationService:
    def __init__(self, engine: RecommendationEngine, explanations: ExplanationProvider):
        self.engine = engine
        self.explanations = explanations

    async def recommend(self, context: RecommendationContext, *, skill_names: dict[str, str] | None = None) -> tuple[ExplainedRecommendation, ...]:
        ranked = self.engine.rank(context)
        if not ranked:
            return ()
        texts = await self.explanations.explain(ExplanationContext(context.locale, ranked, skill_names or {}))
        if set(texts) != {item.event_id for item in ranked} or any(not text.strip() for text in texts.values()):
            raise ValueError("explanation provider violated its contract")
        return tuple(ExplainedRecommendation(item, texts[item.event_id]) for item in ranked)
