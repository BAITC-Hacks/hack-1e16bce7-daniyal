"""Grounded, localized sentences. Models reference facts, never invent numeric prose."""
from dataclasses import dataclass
import math

from app.domain.models import ExplanationContext


@dataclass(frozen=True)
class ExplanationFact:
    fact_id: str
    category: str
    concise: str
    supportive: str


def explanation_facts(context: ExplanationContext) -> dict[str, tuple[ExplanationFact, ...]]:
    if context.locale not in ("ru", "kk", "en"):
        raise ValueError("locale must be ru, kk or en")
    if len(context.recommendations) > 3:
        raise ValueError("at most three recommendations can be explained")
    result = {}
    lang = context.locale
    for rec in context.recommendations:
        if not rec.event_id or rec.event_id in result or not rec.target_grade or not math.isfinite(rec.score):
            raise ValueError("invalid or duplicate ranked recommendation")
        for values in (rec.skill_gaps, rec.expected_gains, rec.current_levels, rec.required_levels):
            if any(not key or type(value) is not int or not 0 <= value <= 5 for key, value in values.items()):
                raise ValueError("invalid skill facts")
        facts = []
        def add(category: str, texts: dict[str, str], alternatives: dict[str, str] | None = None) -> None:
            facts.append(ExplanationFact(f"f{len(facts)}", category, texts[lang], (alternatives or texts)[lang]))

        grade = rec.target_grade
        current = rec.current_grade
        add("grade", {
            "ru": f"Целевой грейд — {grade}." if not current else f"Ваш текущий грейд — {current}, цель — {grade}.",
            "kk": f"Мақсатты деңгей — {grade}." if not current else f"Қазіргі деңгейіңіз — {current}, мақсат — {grade}.",
            "en": f"Your target grade is {grade}." if not current else f"Your current grade is {current}; your target is {grade}.",
        })
        for key, gap in sorted(rec.skill_gaps.items()):
            gain = rec.expected_gains.get(key, 0)
            if gap <= 0 or gain <= 0:
                raise ValueError("each explained gap must have a positive expected gain")
            name = context.skill_names.get(key, key)
            before, required = rec.current_levels.get(key), rec.required_levels.get(key)
            if (before is None) != (required is None):
                raise ValueError("current and required levels must be provided together")
            if before is not None and (required - before != gap or before + gain > 5):
                raise ValueError("inconsistent gap or gain")
            if before is None:
                add("gap", {"ru": f"{name}: до требования {grade} не хватает {gap}.",
                            "kk": f"{name}: {grade} талабына дейінгі айырма — {gap}.",
                            "en": f"{name}: the gap to the {grade} requirement is {gap}."})
            else:
                add("gap", {"ru": f"{name}: текущий уровень {before}, требование {grade} — {required}.",
                            "kk": f"{name}: қазіргі деңгей — {before}, {grade} талабы — {required}.",
                            "en": f"{name}: current level {before}, required level for {grade}: {required}."})
            remaining = max(0, gap - gain)
            add("gain", {
                "ru": f"{name}: ожидаемый рост +{gain}, разрыв сократится с {gap} до {remaining}.",
                "kk": f"{name}: күтілетін өсім +{gain}, айырма {gap} деңгейінен {remaining} деңгейіне азаяды.",
                "en": f"{name}: expected gain +{gain}; the gap falls from {gap} to {remaining}.",
            }, {
                "ru": f"Активность поможет развить {name} на {gain} и уменьшить разрыв с {gap} до {remaining}.",
                "kk": f"Бұл белсенділік {name} дағдысын {gain} деңгейге дамытып, айырманы {gap} деңгейінен {remaining} деңгейіне азайтуға көмектеседі.",
                "en": f"This activity can develop {name} by {gain}, reducing the gap from {gap} to {remaining}.",
            })
        if not rec.skill_gaps:
            raise ValueError("recommendations need grounded skill gaps")
        if (rec.readiness_before is None) != (rec.readiness_after is None):
            raise ValueError("both readiness values are required")
        if rec.readiness_before is not None:
            b, a = rec.readiness_before, rec.readiness_after
            if not (0 <= b <= a <= 100):
                raise ValueError("invalid readiness facts")
            add("readiness", {"ru": f"Расчётная готовность к грейду: {b:g}% → {a:g}%.",
                              "kk": f"Деңгейге есептік дайындық: {b:g}% → {a:g}%.",
                              "en": f"Calculated grade readiness: {b:g}% → {a:g}%."})
        labels = {
            "completed": ("завершено", "аяқталды", "completed"),
            "missed": ("пропущено", "өткізіп алынды", "missed"),
            "no_show": ("неявки", "қатыспады", "no-shows"),
            "dropped": ("прервано", "тоқтатылды", "dropped"),
            "declined": ("отказы", "бас тартылды", "declined"),
            "registered": ("регистрации", "тіркелді", "registered"),
            "in_progress": ("в процессе", "орындалуда", "in progress"),
            "overdue": ("просрочено", "мерзімі өтті", "overdue"),
        }
        index = ("ru", "kk", "en").index(lang)
        parts = []
        for status, count in sorted(rec.history_summary.items()):
            if status not in labels or type(count) is not int or count < 0:
                raise ValueError("invalid history facts")
            if count:
                parts.append(f"{labels[status][index]}: {count}")
        if parts:
            detail = ", ".join(parts)
            caveat = {"ru": "", "kk": "", "en": ""}
            if any(rec.history_summary.get(status, 0) for status in ("missed", "no_show", "dropped", "declined")):
                caveat = {"ru": " Причины незавершения неизвестны.",
                          "kk": " Аяқталмау себептері белгісіз.",
                          "en": " Reasons for non-completion are unknown."}
            add("history", {"ru": f"История активностей этого типа — {detail}." + caveat["ru"],
                            "kk": f"Осы түрдегі белсенділіктер тарихы — {detail}." + caveat["kk"],
                            "en": f"History for this activity type — {detail}." + caveat["en"]})
        result[rec.event_id] = tuple(facts)
    return result
