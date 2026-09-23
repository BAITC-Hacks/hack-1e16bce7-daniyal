from collections.abc import Mapping, Sequence
from app.domain.models import SkillEffect


def apply_skill_effects(
    skills: Mapping[str, int], effects: Sequence[SkillEffect]
) -> dict[str, int]:
    """Preview a completion; persistence/idempotency belong in the service.

    Missing skills are not silently interpreted as zero. The importer must
    resolve that policy from the dataset README before applying effects.
    """
    if any(type(value) is not int or not 0 <= value <= 5 for value in skills.values()):
        raise ValueError("skill levels must be integers between 0 and 5")
    if len({effect.skill_id for effect in effects}) != len(effects):
        raise ValueError("duplicate skill effects")
    result = dict(skills)
    for effect in effects:
        if effect.skill_id not in result:
            raise ValueError(f"unknown employee skill: {effect.skill_id}")
        current = result[effect.skill_id]
        result[effect.skill_id] = max(current, min(current + effect.gain, effect.max_level, 5))
    return result
