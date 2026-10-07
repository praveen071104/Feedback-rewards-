"""Deterministic triage driven by `absa.analyse`.

Rules (keep in sync with the LLM contract documented in `triage.py`):
  - gibberish          -> ignore, no ticket, no reward.
    - serious_complaint  -> safety/legal/financial cue OR very negative aspect with impact.
                                                    Opens an assigned high-priority ticket; genuine feedback gets high tier.
    - minor_complaint    -> overall negative or any negative aspect.
                                                    Opens ticket when detail is present; no reward unless loyal.
  - major_compliment   -> overall positive AND specific aspect praise.
  - minor_compliment   -> positive but generic / low word count.
"""
from __future__ import annotations

from app.llm import absa
from app.llm import detail as detail_mod
from app.llm.replies import compose


def _reply(category: str, needs_ticket: bool, reward_tier: str) -> str:
    pieces = []
    if category == "serious_complaint":
        pieces.append("We're really sorry — thank you for telling us. This is serious to us.")
    elif category == "minor_complaint":
        pieces.append("Thank you for letting us know, and we're sorry for the inconvenience.")
    elif category == "major_compliment":
        pieces.append("Thank you so much — we love hearing this.")
    elif category == "minor_compliment":
        pieces.append("Thank you for the kind words.")
    else:
        pieces.append("Thanks for your submission.")
    if needs_ticket:
        pieces.append("A member of our team will look into it and get in touch.")
    if reward_tier != "none":
        pieces.append("A colleague will review the pound-denominated incentive recommendation.")
    return " ".join(pieces)


def _summary(category: str, text: str, aspects: list[dict]) -> str:
    label = {
        "minor_compliment": "Compliment",
        "major_compliment": "Strong praise",
        "minor_complaint": "Minor issue",
        "serious_complaint": "Serious issue",
        "gibberish": "Gibberish",
    }[category]
    if aspects:
        focus = ", ".join(a["aspect"].replace("_", " ") for a in aspects[:2])
        label = f"{label} [{focus}]"
    snippet = " ".join((text or "").split())[:120]
    return f"{label}: {snippet}" if snippet else label


def _decide(result: absa.ABSAResult, stars: int) -> tuple[str, bool]:
    """Return (category, genuine)."""
    if result.is_gibberish:
        return "gibberish", False

    negative_aspects = [a for a in result.aspects if a.sentiment == "negative"]
    positive_aspects = [a for a in result.aspects if a.sentiment == "positive"]

    if result.has_serious_cue:
        return "serious_complaint", True
    if result.overall_score <= -0.6 and len(negative_aspects) >= 2:
        return "serious_complaint", True

    if negative_aspects or result.overall_sentiment == "negative" or stars <= 2:
        return "minor_complaint", True

    if positive_aspects and result.overall_score >= 0.5 and result.word_count >= 8:
        return "major_compliment", True
    if result.overall_sentiment == "positive" or stars >= 4:
        return "minor_compliment", True

    return "minor_compliment", True


def scripted_responder(task: str, payload: dict, _tools: dict) -> dict:
    if task != "triage":
        return {}
    text = str(payload.get("feedback", ""))
    stars = int(payload.get("stars", 3))

    result = absa.analyse(text)
    category, genuine = _decide(result, stars)
    aspects_dicts = [
        {"aspect": a.aspect, "sentiment": a.sentiment, "score": a.score, "evidence": a.evidence}
        for a in result.aspects
    ]

    detail = detail_mod.assess(text, aspects_dicts, serious_cue=result.has_serious_cue)
    has_detail = detail["detailed"]
    needs_ticket = category == "serious_complaint" or (category == "minor_complaint" and has_detail)

    if category == "serious_complaint":
        priority = "high"
        reward_tier = "high" if genuine else "none"
    elif category == "major_compliment":
        priority = "low"
        reward_tier = "mid" if genuine else "none"
    elif category == "minor_complaint":
        priority = "medium" if needs_ticket else "low"
        reward_tier = "none"
    else:
        priority = "low"
        reward_tier = "none"
    if genuine and payload.get("sparks_member"):
        reward_tier = "high"

    return {
        "category": category,
        "genuine": genuine,
        "has_sufficient_detail": has_detail,
        "detail": detail,
        "reward_tier": reward_tier,
        "needs_ticket": needs_ticket,
        "priority": priority,
        "customer_reply": compose(
            category=category, text=text, aspects=aspects_dicts, detailed=has_detail,
            missing=detail["missing"], needs_ticket=needs_ticket, reward_tier=reward_tier,
        ),
        "staff_summary": _summary(category, text, aspects_dicts),
        "aspects": aspects_dicts,
        "overall_sentiment": result.overall_sentiment,
        "overall_score": result.overall_score,
    }
