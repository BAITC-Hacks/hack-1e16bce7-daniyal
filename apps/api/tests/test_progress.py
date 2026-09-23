import pytest

from app.domain.models import SkillEffect
from app.domain.progress import apply_skill_effects


def test_gain_is_capped_and_input_is_unchanged():
    skills = {"design": 2, "python": 5}
    assert apply_skill_effects(skills, [SkillEffect("design", 3, 4)]) == {"design": 4, "python": 5}
    assert skills == {"design": 2, "python": 5}


def test_activity_never_reduces_an_existing_skill():
    assert apply_skill_effects({"x": 4}, [SkillEffect("x", 1, 3)]) == {"x": 4}


def test_unknown_skills_and_duplicate_effects_are_rejected():
    for effects in ([SkillEffect("missing", 1, 5)], [SkillEffect("x", 1, 5)] * 2):
        with pytest.raises(ValueError):
            apply_skill_effects({"x": 2}, effects)


def test_invalid_levels_and_effects_are_rejected():
    for value in (-1, 6, True, 1.5):
        with pytest.raises(ValueError):
            apply_skill_effects({"x": value}, [])
        with pytest.raises(ValueError):
            SkillEffect("x", value, 5)
