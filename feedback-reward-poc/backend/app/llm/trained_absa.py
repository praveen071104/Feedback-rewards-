"""Inference wrapper using the trained aspect-aware models.

- Prepends STARS_N token so the models can condition on the rating.
- Hard lexicon gate: aspects can only be emitted when a word from
  `absa.ASPECTS` appears in the text, preventing hallucinated aspects.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

import joblib

from app.llm import absa
from app.llm import detail as detail_mod
from app.llm.replies import compose

_BUNDLE_PATH_DEFAULT = Path(__file__).resolve().parent.parent.parent / "data" / "absa_models.joblib"


class _ModelCache:
    def __init__(self):
        self._bundle: dict[str, Any] | None = None
        self._lock = threading.Lock()
        self._path = _BUNDLE_PATH_DEFAULT

    def set_path(self, path: Path) -> None:
        with self._lock:
            if path != self._path:
                self._path = path
                self._bundle = None

    def get(self) -> dict[str, Any]:
        with self._lock:
            if self._bundle is None:
                if not self._path.exists():
                    raise FileNotFoundError(
                        f"Trained model bundle not found at {self._path}. "
                        f"Run `python -m app.llm.data_gen` then `python -m app.llm.train_absa` first."
                    )
                self._bundle = joblib.load(self._path)
            return self._bundle


_cache = _ModelCache()

PRIORITY_FOR_CATEGORY = {
    "serious_complaint": "high",
    "minor_complaint": "medium",
    "major_compliment": "low",
    "minor_compliment": "low",
    "gibberish": "low",
}

REWARD_TIER_FOR_CATEGORY = {
    "serious_complaint": "high",
    "major_compliment": "mid",
    "minor_complaint": "none",
    "minor_compliment": "none",
    "gibberish": "none",
}


def _stars_prefix(stars: int) -> str:
    try:
        n = int(stars)
    except (TypeError, ValueError):
        n = 3
    n = max(1, min(5, n))
    return f"STARS_{n}"


_CLAUSE_SPLIT = re.compile(r"[.!?;,\n]+|\bbut\b|\bhowever\b|\balthough\b|\bthough\b|\byet\b|\band\b", re.IGNORECASE)


def _clauses(text: str) -> list[str]:
    parts = [c.strip() for c in _CLAUSE_SPLIT.split(text) if c and c.strip()]
    if not parts:
        return [text]
    # A tiny fragment with no product/service word ("... and useless") belongs to the clause before it.
    merged: list[str] = []
    for p in parts:
        orphan = len(p.split()) <= 3 and not any(_aspect_keywords_in(a, p) for a in absa.ASPECTS)
        if merged and orphan:
            merged[-1] = f"{merged[-1]} and {p}"
        else:
            merged.append(p)
    return merged


def _aspect_keywords_in(aspect: str, text: str) -> bool:
    low = text.lower()
    for kw in absa.ASPECTS.get(aspect, []):
        if re.search(rf"\b{re.escape(kw.lower())}\b", low):
            return True
    return False


def _clause_for_aspect(aspect: str, clauses: list[str], full_text: str) -> str:
    """Return the clause that mentions the aspect; fall back to the full text."""
    for c in clauses:
        if _aspect_keywords_in(aspect, c):
            return c
    return full_text


NEG_THRESHOLD = 0.60  # below this, any call is treated as neutral (not sure)


def _predict_aspects(bundle: dict, text: str, stars: int) -> tuple[list[dict], list[dict]]:
    """Split into sentences, route each to its aspects, classify each pair.

    Returns (aspects, sentence_trace). The same aspect can appear twice when two
    different sentences talk about it."""
    classes: list[str] = bundle["presence_classes"]
    vec = bundle["vectorizer"]
    sentiment = bundle["sentiment_clf"]
    token = bundle["aspect_token"]
    sent_classes = list(sentiment.classes_)

    aspects: list[dict] = []
    trace: list[dict] = []
    for clause in _clauses(text):
        subject_text = re.sub(
            r"\b(?:at|in|near|by|from|on) (?:the|our|your|a) "
            r"(?:checkout|till|store|shop|food hall|bakery|returns desk)\b",
            "", clause, flags=re.IGNORECASE,
        )
        presence = bundle["presence_clf"].predict_proba(
            vec.transform([f"{_stars_prefix(3)} {subject_text}"])
        )[0]
        hits = [a for a, probability in zip(classes, presence)
                if probability >= 0.5 and _aspect_keywords_in(a, subject_text)]
        if not hits:
            trace.append({"sentence": clause, "aspect": None, "sentiment": None,
                          "confidence": None, "note": "No product or service mentioned"})
            continue
        for a in hits:
            Xa = vec.transform([f"{token}_{a} {_stars_prefix(3)} {clause}"])
            probs = sentiment.predict_proba(Xa)[0]
            idx = int(probs.argmax())
            label, conf, note = sent_classes[idx], round(float(probs[idx]), 3), ""
            score = absa.sentiment_score(clause)
            text_label = "positive" if score >= 0.3 else ("negative" if score <= -0.3 else "neutral")
            if text_label != "neutral" and label != text_label:
                label = text_label
                note = "Clear text sentiment overrides the rating-conditioned model; colleague review required"
            elif not absa.has_sentiment_evidence(clause):
                label = "neutral"
                note = "An aspect is mentioned without a supported positive or negative opinion"
            elif label != "neutral" and conf < NEG_THRESHOLD:
                note = f"Only {int(conf * 100)}% sure it is {label}, so treated as neutral"
                label = "neutral"
            aspects.append({"aspect": a, "sentiment": label, "confidence": conf,
                            "score": score, "evidence": clause[:160]})
            trace.append({"sentence": clause, "aspect": a, "sentiment": label,
                          "confidence": conf, "note": note})
    return aspects, trace


def _reply(category: str, needs_ticket: bool, reward_tier: str) -> str:
    pieces = []
    if category == "serious_complaint":
        pieces.append("We're so sorry. This isn't the standard we expect, and we're grateful you told us.")
    elif category == "minor_complaint":
        pieces.append("Thank you for letting us know, and we're sorry we let you down.")
    elif category == "major_compliment":
        pieces.append("Thank you, this really made our day. We'll share your kind words with the team.")
    elif category == "minor_compliment":
        pieces.append("Thank you for your kind words.")
    else:
        pieces.append("Thanks for getting in touch.")
    if needs_ticket:
        pieces.append("One of our colleagues will look into this and be in touch.")
    if reward_tier != "none":
        pieces.append("A colleague will review your feedback and, if it qualifies, add the reward to your Sparks wallet.")
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


def trained_responder(task: str, payload: dict, _tools: dict) -> dict:
    if task != "triage":
        return {}

    text = str(payload.get("feedback", ""))
    stars = int(payload.get("stars", 3))

    heuristic = absa.analyse(text)
    bundle = _cache.get()

    prefixed = f"{_stars_prefix(stars)} {text}"
    X = bundle["vectorizer"].transform([prefixed])
    cat_clf = bundle["category_clf"]
    category = cat_clf.predict(X)[0]
    category_confidence = 0.0
    if hasattr(cat_clf, "predict_proba"):
        probs = cat_clf.predict_proba(X)[0]
        classes = list(cat_clf.classes_)
        category_confidence = round(float(probs[classes.index(category)]), 3)
    model_category = str(category)
    model_override = False
    if heuristic.has_serious_cue:
        if category != "serious_complaint":
            model_override = True
        category = "serious_complaint"
    if heuristic.is_gibberish:
        category = "gibberish"

    aspects, sentence_trace = _predict_aspects(bundle, text, stars)

    # The words of the review win over the star rating when they clearly disagree.
    consistency_note = ""
    pos_n = sum(a["sentiment"] == "positive" for a in aspects)
    neg_n = sum(a["sentiment"] == "negative" for a in aspects)
    mixed = pos_n > 0 and neg_n > 0
    rating_mismatch = False
    if category == "serious_complaint" and not heuristic.has_serious_cue:
        category = "minor_complaint" if neg_n or heuristic.overall_sentiment == "negative" else "minor_compliment"
        consistency_note = "No supported safety, legal, financial or unresolved-issue evidence for a serious complaint"
    if category in ("minor_compliment", "major_compliment") and neg_n >= 1:
        worst = next(a for a in aspects if a["sentiment"] == "negative")
        category = "minor_complaint"
        consistency_note = f"The wording is negative about {worst['aspect'].replace('_', ' ')}, so it is treated as a complaint"
    elif category == "minor_complaint" and pos_n >= 1 and neg_n == 0:
        best = next(a for a in aspects if a["sentiment"] == "positive")
        category = "minor_compliment"
        consistency_note = f"The wording is positive about {best['aspect'].replace('_', ' ')}, so it is treated as a compliment"
    if (stars >= 4 and neg_n >= 1 and pos_n == 0) or (stars <= 2 and pos_n >= 1 and neg_n == 0):
        rating_mismatch = True
        consistency_note += f". The {stars}-star rating disagrees with the wording, which was followed"
    positive_topics = {a["aspect"] for a in aspects if a["sentiment"] == "positive"}
    if category == "minor_compliment" and len(positive_topics) >= 2 and neg_n == 0 and absa.PRAISE_PATTERNS.search(text):
        category, consistency_note = "major_compliment", "Several specific things praised, with no complaints"
    model_override = model_override or category != model_category
    if hasattr(cat_clf, "predict_proba"):
        category_confidence = round(float(probs[classes.index(category)]), 3)

    detail = detail_mod.assess(text, aspects, serious_cue=heuristic.has_serious_cue or category == "serious_complaint")
    has_detail = detail["detailed"]
    needs_ticket = category == "serious_complaint" or (category == "minor_complaint" and has_detail)
    genuine = category != "gibberish"

    reward_eligible = genuine
    reward_tier = REWARD_TIER_FOR_CATEGORY[category] if reward_eligible else "none"
    priority = PRIORITY_FOR_CATEGORY[category]
    if category == "minor_complaint" and not needs_ticket:
        priority = "low"

    # Low model confidence -> flag for closer colleague review.
    needs_review = bool(category_confidence < 0.55 or mixed or rating_mismatch or model_override
                        or any("review required" in sentence["note"] for sentence in sentence_trace))

    if heuristic.is_gibberish:
        category_reason = "Too short or not readable as feedback"
    elif heuristic.has_serious_cue:
        category_reason = "Safety, legal or money wording found, so treated as serious"
    elif consistency_note:
        category_reason = consistency_note.strip(". ").strip()
    elif mixed:
        good = ", ".join(sorted({a["aspect"].replace("_", " ") for a in aspects if a["sentiment"] == "positive"}))
        bad = ", ".join(sorted({a["aspect"].replace("_", " ") for a in aspects if a["sentiment"] == "negative"}))
        category_reason = f"Mixed review: praise for {good}, but a problem with {bad}. A colleague should read it"
    else:
        category_reason = f"Language pattern and {stars}-star rating point to this category"
    if needs_ticket:
        ticket_reason = "Serious issue, so a ticket is always opened" if category == "serious_complaint" else "Complaint with enough detail to act on"
    elif category == "minor_complaint":
        ticket_reason = "Not enough detail to act on yet, so the customer is asked for more"
    else:
        ticket_reason = "Nothing to put right"
    asks = ", ".join(c["label"].lower() for c in detail["checks"] if not c["met"])
    if reward_tier == "high":
        reward_reason = "Genuine serious complaint qualifies for the high tier"
    elif reward_tier == "mid":
        reward_reason = "Genuine major compliment qualifies for the mid tier"
    elif category == "minor_complaint":
        reward_reason = "No incentive for a minor complaint unless the customer is a loyal Sparks member"
    elif reward_tier != "none":
        reward_reason = {
            "low": "Low-tier incentive recommended",
            "mid": "Genuine major compliment qualifies for the mid tier",
            "high": "Genuine serious complaint qualifies for the high tier",
        }[reward_tier]
    elif category == "minor_compliment":
        reward_reason = "Kind words are appreciated; a genuine Sparks member qualifies for high tier"
    else:
        reward_reason = "No reward recommended"
    trace = {
        "sentences": sentence_trace,
        "category": category,
        "category_confidence": category_confidence,
        "model_category": model_category,
        "model_override": model_override,
        "category_reason": category_reason,
        "stars_used": stars,
        "detail": detail,
        "ticket": {"opened": needs_ticket, "reason": ticket_reason},
        "reward": {"tier": reward_tier, "reason": reward_reason},
        "review_flag": needs_review,
        "rating_mismatch": rating_mismatch,
    }

    if aspects and (pos_n or neg_n):
        overall = "mixed" if mixed else ("positive" if pos_n else "negative")
    elif aspects:
        overall = "neutral"
    else:
        overall = heuristic.overall_sentiment

    return {
        "category": category,
        "category_confidence": category_confidence,
        "genuine": genuine,
        "has_sufficient_detail": has_detail,
        "reward_tier": reward_tier,
        "needs_ticket": needs_ticket,
        "needs_review": needs_review,
        "model_override": model_override,
        "priority": priority,
        "customer_reply": compose(
            category=category, text=text, aspects=aspects, detailed=has_detail, missing=detail["missing"],
            needs_ticket=needs_ticket, reward_tier=reward_tier,
        ),
        "staff_summary": _summary(category, text, aspects),
        "aspects": aspects,
        "detail": detail,
        "trace": trace,
        "overall_sentiment": overall,
        "overall_score": heuristic.overall_score,
    }


def set_bundle_path(path: Path) -> None:
    _cache.set_path(path)


def ensure_loaded() -> dict[str, Any]:
    """Pre-warm the model (used at app startup for faster first request)."""
    return _cache.get()


def load_metrics(metrics_path: Path | None = None) -> dict:
    p = metrics_path or (_BUNDLE_PATH_DEFAULT.parent / "absa_metrics.json")
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))
