import asyncio
from dataclasses import replace
from datetime import datetime, time, timedelta
from pathlib import Path
import shutil
import json

import pytest

from app.application.recommendations import RecommendationService
from app.domain.models import Participation
from app.domain.progress import apply_skill_effects
from app.domain.ranking import DeterministicRecommendationEngine
from app.infrastructure.ai_dataset import DatasetSnapshot
from app.infrastructure.explanations import TemplateExplanationProvider

DATASET = Path(__file__).resolve().parents[3] / "dataset"


@pytest.fixture(scope="module")
def dataset():
    return DatasetSnapshot.load(DATASET)


def test_all_profiles_have_valid_deterministic_results_and_localized_fallback(dataset):
    engine = DeterministicRecommendationEngine()
    service = RecommendationService(engine, TemplateExplanationProvider())
    async def run():
        assert len(dataset.employees) == 200 and len(dataset.history) == 2743
        for employee_id in dataset.employees:
            for locale in ("ru", "kk", "en"):
                context = dataset.context_for(employee_id, locale)
                result = await service.recommend(context, skill_names=dataset.skill_names)
                assert len(result) <= 3
                assert tuple(row.facts for row in result) == engine.rank(context)
                assert len({row.facts.event_id for row in result}) == len(result)
                for row in result:
                    event = dataset.events[row.facts.event_id]
                    assert not event.mandatory
                    assert row.facts.readiness_after >= row.facts.readiness_before
                    assert row.explanation
                    assert dataset.employees[employee_id].employee_id not in row.explanation
    asyncio.run(run())


def test_assessment_reconstruction_applies_only_later_completions_once(dataset):
    employee = dataset.employees["E0028"]
    event = next(event for event in dataset.events.values() if event.effects and not event.mandatory)
    baseline = {key: employee.skills.get(key, 0) for key in dataset.skill_names}
    older = Participation("old", employee.employee_id, event.event_id, "completed",
                          datetime.combine(employee.last_review_date, time.min))
    later = replace(older, participation_id="new", occurred_at=older.occurred_at + timedelta(days=1))
    assert replace(dataset, history=(older,)).context_for(employee.employee_id).employee.skills == baseline
    expected = apply_skill_effects(baseline, event.effects)
    assert replace(dataset, history=(later,)).context_for(employee.employee_id).employee.skills == expected


def test_new_judge_profile_without_hardcoded_employee_ids(dataset):
    employee = dataset.employees["E0028"].model_copy(update={"employee_id": "JURY_NEW"})
    snapshot = replace(dataset, employees={employee.employee_id: employee}, history=())
    context = snapshot.context_for(employee.employee_id)
    assert context.employee.employee_id == "JURY_NEW"
    assert context.history == ()
    assert DeterministicRecommendationEngine().rank(context)


def test_current_skills_are_not_replayed_by_service(dataset):
    context = dataset.context_for("E0028")
    event = dataset.events[DeterministicRecommendationEngine().rank(context)[0].event_id]
    after = apply_skill_effects(context.employee.skills, event.effects)
    completed = Participation("new_completion", context.employee.employee_id, event.event_id, "completed",
                              datetime.combine(dataset.as_of, time.min))
    updated = replace(context, employee=replace(context.employee, skills=after), history=(*context.history, completed))
    result = DeterministicRecommendationEngine().rank(updated)
    assert all(row.event_id != event.event_id for row in result)
    assert updated.employee.skills == after


@pytest.mark.parametrize("bad", ["unknown_skill", "duplicate_employee", "unknown_event", "unknown_status"])
def test_invalid_dataset_rejected(tmp_path, bad):
    for name in ("skills.json", "employees.json", "events.json", "activity_history.csv"):
        shutil.copyfile(DATASET / name, tmp_path / name)
    path = tmp_path / "employees.json"
    if bad in ("unknown_skill", "duplicate_employee"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if bad == "unknown_skill":
            data["employees"][0]["skills"]["FAKE"] = 2
        else:
            data["employees"].append(data["employees"][0])
        path.write_text(json.dumps(data), encoding="utf-8")
    else:
        path = tmp_path / "activity_history.csv"
        text = path.read_text(encoding="utf-8")
        text = text.replace("EV_001", "FAKE", 1) if bad == "unknown_event" else text.replace("completed", "fiction", 1)
        path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        DatasetSnapshot.load(tmp_path)


def test_service_rejects_invalid_explanation_ids(dataset):
    class BadProvider:
        async def explain(self, context):
            return {"invented": "invalid"}
    with pytest.raises(ValueError):
        asyncio.run(RecommendationService(DeterministicRecommendationEngine(), BadProvider()).recommend(dataset.context_for("E0028")))
