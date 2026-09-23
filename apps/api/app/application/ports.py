from typing import Mapping, Protocol

from app.domain.models import ExplanationContext, RankedRecommendation, RecommendationContext


class RecommendationEngine(Protocol):
    """Pure Python scoring: same input yields the same ordered facts, no network."""

    def rank(self, context: RecommendationContext) -> tuple[RankedRecommendation, ...]: ...


class ExplanationProvider(Protocol):
    """Explain facts only; cannot alter scores, gains or selection.

    Return text keyed by event_id. RecommendationService validates IDs
    and joins explanations to the original ranked facts.
    """

    async def explain(self, context: ExplanationContext) -> Mapping[str, str]: ...
