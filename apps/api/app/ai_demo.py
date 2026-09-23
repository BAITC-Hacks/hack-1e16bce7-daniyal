"""Run from apps/api: python -m app.ai_demo --employee E0028 --locale ru."""
import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import sys

from app.domain.models import ExplanationContext
from app.domain.ranking import DeterministicRecommendationEngine, career_readiness
from app.infrastructure.ai_dataset import DatasetSnapshot
from app.infrastructure.explanations import ExplanationSettings, OpenAIExplanationProvider


async def run(args):
    dataset = DatasetSnapshot.load(args.dataset)
    context = dataset.context_for(args.employee, args.locale)
    ranked = DeterministicRecommendationEngine().rank(context)
    settings = ExplanationSettings()
    if not args.live:
        settings = settings.model_copy(update={"llm_enabled": False})
    provider = OpenAIExplanationProvider(settings)
    explained = await provider.explain_with_metadata(ExplanationContext(context.locale, ranked, dataset.skill_names))
    print(json.dumps({
        "employee_id": args.employee, "locale": context.locale,
        "readiness": career_readiness(context.employee.skills, context.target),
        "explanation_source": explained.source, "fallback_reason": explained.fallback_reason,
        "recommendations": [{**asdict(item), "explanation": explained.texts[item.event_id]} for item in ranked],
    }, ensure_ascii=False, indent=2))
    if args.live and ranked and explained.source != "openai":
        raise SystemExit(2)  # A live smoke test must not silently pass on fallback.


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parents[3] / "dataset")
    parser.add_argument("--employee", default="E0028")
    parser.add_argument("--locale", choices=("ru", "kk", "en"))
    parser.add_argument("--live", action="store_true", help="Call OpenAI; default is offline")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, f"Dataset/configuration error: {type(error).__name__}\n")


if __name__ == "__main__":
    main()
