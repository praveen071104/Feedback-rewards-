"""Lightweight Aspect-Based Sentiment Analysis for retail feedback.

Pipeline (pure Python; no network, no model download):
  1. Split feedback into clauses on sentence breaks and contrast markers.
  2. Score each clause with VADER (compound in [-1, 1]).
  3. Match aspect keywords (retail lexicon) within each clause.
  4. Attribute the clause's sentiment to every aspect it mentions.
  5. Aggregate per-aspect sentiments, keep the strongest evidence clause.
  6. Return overall sentiment + list of (aspect, sentiment, score, evidence).

This is a transparent baseline. It is not a trained ABSA model; it will miss
sarcasm, implicit aspects, and complex negation. We expose the aspects to staff
so decisions remain auditable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


# ---- Retail aspect lexicon -------------------------------------------------

ASPECTS: dict[str, list[str]] = {
    "product_quality": [
        "product", "item", "quality", "food", "meal", "sandwich", "bread", "cake",
        "milk", "clothes", "clothing", "shirt", "jeans", "dress", "jacket",
        "shoes", "stale", "fresh", "mouldy", "mould", "mold", "broken",
        "damaged", "faulty", "defective", "allergen", "allergic",
        "trousers", "cardigan", "strawberries", "biscuits", "yogurt", "ham",
        "jumper", "coat", "blouse", "chicken", "salad", "fabric", "stitching",
        "waistband", "sizing", "fit", "fitting", "fitted", "true to size", "size", "sizes",
        "caterpillar", "dine in", "fresh produce", "per una", "autograph",
        "ready meal", "dessert", "fruit", "percy pigs", "colin",
    ],
    "availability": [
        "stock", "sold out", "out of stock", "unavailable", "shelf", "shelves",
        "restock", "available", "my size", "colour",
        "color", "variety", "stocks", "stocked",
    ],
    "staff_service": [
        "staff", "colleague", "colleagues", "employee", "manager", "assistant",
        "cashier", "rude", "helpful", "friendly", "freindly", "unfriendly", "unhelpful",
        "polite", "impolite", "ignored", "attentive", "service", "team",
    ],
    "checkout_payment": [
        "checkout", "till", "queue", "queues", "que", "waited", "waiting", "wait",
        "card", "payment", "cash", "receipt", "overcharged",
        "charged twice", "double charged", "unauthorised charge", "unauthorized charge",
        "scan", "scanner",
    ],
    "delivery_online": [
        "delivery", "delivered", "arrived", "didn't arrive", "did not arrive",
        "online order", "order", "parcel", "tracking", "driver", "courier",
        "late delivery", "missing order", "click & collect", "click and collect",
        "click-and-collect", "collect",
    ],
    "returns_refund": [
        "return", "returned", "refund", "exchange", "replacement", "refused",
        "returns desk", "returns",
    ],
    "store_environment": [
        "store", "shop", "aisle", "lighting", "light", "bright", "dim", "dark",
        "dirty", "clean", "cleanliness", "smell", "odour", "odor", "tidy",
        "messy", "cold", "hot", "temperature", "layout", "signage", "sign",
        "signs", "music", "noisy", "crowded", "atmosphere",
    ],
    "price_value": [
        "price", "prices", "expensive", "cheap", "value", "cost", "pricey",
        "overpriced", "affordable", "bargain", "deal", "pricing",
    ],
    "accessibility": [
        "wheelchair", "ramp", "accessible", "accessibility", "disabled",
        "inaccessible", "blocked entrance", "step", "steps", "lift", "elevator",
    ],
    "online_app": [
        "app", "website", "site", "online account", "mobile app", "login",
        "log in", "web page", "webpage", "online experience", "browser",
        "checkout page", "error message", "crashed", "glitch", "bug",
    ],
    "loyalty_sparks": [
        "sparks", "points", "rewards", "reward", "offers", "offer", "voucher",
        "vouchers", "loyalty", "members", "membership", "discount", "coupon",
        "wallet", "stamps", "stamp",
    ],
    "gifting": [
        "gift", "gifts", "gift card", "giftcard", "flowers", "bouquet",
        "hamper", "present", "wrapping", "gift wrap",
    ],
}

# Serious-impact cues override polarity: these are always serious concerns.
SERIOUS_CUES = re.compile(
    r"\b(allergic reaction|undeclared allergens?|missing allergen information|anaphyla\w*|"
    r"food poison\w*|injur\w*|hospital\w*|ambulance|"
    r"(?:I|we|my (?:child|son|daughter)) (?:was|were|am|became|felt|started) "
    r"(?:violently )?(?:sick|unwell|vomit\w*)|"
    r"(?:made|left) (?:me|us|my child) (?:sick|unwell)|"
    r"(?:did not|didn't|failed to) (?:list|declare|label|mention) (?:the |an |any )?allergens?|"
    r"allergens?[^.!?\n]{0,30}not (?:labelled|labeled|declared)|"
    r"(?:allerg\w*|nuts|sesame|eggs)[^.!?\n]{0,100}(?:had|caused|triggered) (?:an? )?(?:allergic )?reaction|"
    r"(?:fell|slipped) on (?:the |a )?(?:wet floor|stairs|escalator)|"
    r"(?:broken|sharp|shattered) glass|glass (?:shards?|fragments?)|"
    r"glass (?:in|inside) (?:my |the |a |our )?(?:food|meal|sandwich|bread|cake|salad)|"
    r"metal fragments?|mould\w*|mold\w*|bleed\w*|burn\w*|choking|choked|"
    r"discriminat\w*|racis\w*|harass\w*|threat\w*|assault\w*|stolen|theft|fraud|"
    r"abusive|unauthori[sz]ed charge|charged twice|double charged|weeks? (?:now|without)|"
    r"months? (?:now|without)|"
    r"still waiting (?:for|on) (?:my |the |a |our )?(?:refund|order|delivery|response|reply)|"
    r"never (?:came|arrived|received|replied|responded)|"
    r"no (?:response|reply|refund)|refund (?:never|still))\b",
    re.IGNORECASE,
)

# Explicit customer-pain patterns that force a clause to negative (overrides a
# naive positive lexicon score, e.g. "the light was too bright").
PAIN_PATTERNS = re.compile(
    r"\b(couldn't|cannot|could not|can't|hurt|hurts|hurting|painful|strain\w*|"
    r"too (?:bright|dim|dark|loud|noisy|cold|hot|slow|dirty|messy|crowded|expensive)|"
    r"sold out|unavailable|not available|out of stock|didn't arrive|did not arrive|"
    r"never (?:came|arrived|received|replied|responded)|still waiting)\b",
    re.IGNORECASE,
)

# Praise phrases VADER underweights.
PRAISE_PATTERNS = re.compile(
    r"\b(above and beyond|exceptional|outstanding|went out of (?:her|his|their) way|"
    r"amazing|brilliant|fantastic|wonderful|extraordinary|life[- ]?saver|"
    r"saved (?:me|us|the day)|highly recommend|absolutely love|best (?:experience|service|visit))\b",
    re.IGNORECASE,
)

# Keywords that materially add detail (anchor it in time/place/action).
DETAIL_CUES = re.compile(
    r"\b(yesterday|today|this morning|this afternoon|this evening|last week|"
    r"last month|at (?:the )?(?:till|checkout|counter|cafe|aisle|food hall)|"
    r"manager|colleague|staff member|named|called|order (?:number|#)|"
    r"receipt|tracking)\b",
    re.IGNORECASE,
)

CLAUSE_SPLIT = re.compile(r"[.!?;\n]+|\bbut\b|\bhowever\b|\balthough\b|\bthough\b", re.IGNORECASE)

GIBBERISH = re.compile(r"^\W*$|^(?:asdf|qwer|test\s*test|lorem).{0,20}$", re.IGNORECASE)

NON_ISSUE_CUES = re.compile(
    r"\bno (?:refund|return|injury|allergic reaction|complaint|problem) "
    r"(?:(?:is|was) )?(?:needed|required|necessary)\b|"
    r"\b(?:not|never) (?:injured|hospitali[sz]ed|charged twice|double charged)\b",
    re.IGNORECASE,
)


# ---- Public types ----------------------------------------------------------

@dataclass
class AspectVerdict:
    aspect: str
    sentiment: str  # positive | neutral | negative
    score: float    # VADER compound in [-1, 1]
    evidence: str   # short clause that triggered it


@dataclass
class ABSAResult:
    overall_sentiment: str          # positive | neutral | negative
    overall_score: float            # compound in [-1, 1]
    aspects: list[AspectVerdict]
    has_serious_cue: bool
    has_detail: bool
    word_count: int
    is_gibberish: bool


# ---- Engine ----------------------------------------------------------------

_vader = SentimentIntensityAnalyzer()
_vader.lexicon.update({"stale": -2.0, "faulty": -2.0, "mouldy": -2.5, "unhelpful": -2.0})


def has_serious_cue(text: str) -> bool:
    return bool(SERIOUS_CUES.search(NON_ISSUE_CUES.sub("", text)))


def has_sentiment_evidence(text: str) -> bool:
    cleaned = NON_ISSUE_CUES.sub("", text)
    tokens = re.findall(r"[\w']+", cleaned.lower())
    return bool(PAIN_PATTERNS.search(cleaned) or PRAISE_PATTERNS.search(cleaned)) or any(
        _vader.lexicon.get(token, 0) != 0 for token in tokens
    )


def sentiment_score(text: str) -> float:
    cleaned = NON_ISSUE_CUES.sub("", text)
    score = _vader.polarity_scores(cleaned)["compound"]
    if PAIN_PATTERNS.search(cleaned) and score > -0.2:
        score = min(score - 0.5, -0.3)
    elif PRAISE_PATTERNS.search(cleaned) and score < 0.4:
        score = max(score + 0.5, 0.5)
    return round(score, 3)


def _label(compound: float) -> str:
    if compound >= 0.05:
        return "positive"
    if compound <= -0.05:
        return "negative"
    return "neutral"


def _clauses(text: str) -> list[str]:
    return [c.strip() for c in CLAUSE_SPLIT.split(text) if c.strip()]


def _match_aspects(clause: str) -> list[str]:
    low = clause.lower()
    hits: list[str] = []
    for aspect, keywords in ASPECTS.items():
        if any(re.search(rf"\b{re.escape(k)}\b", low) for k in keywords):
            hits.append(aspect)
    return hits


def analyse(text: str) -> ABSAResult:
    text = text.strip()
    word_count = len(re.findall(r"\w+", text))
    if word_count < 2 or GIBBERISH.match(text):
        return ABSAResult(
            overall_sentiment="neutral",
            overall_score=0.0,
            aspects=[],
            has_serious_cue=False,
            has_detail=False,
            word_count=word_count,
            is_gibberish=True,
        )

    overall = sentiment_score(text)

    aspects: dict[str, AspectVerdict] = {}

    for clause in _clauses(text):
        score = sentiment_score(clause)
        for aspect in _match_aspects(clause):
            prev = aspects.get(aspect)
            if prev is None or abs(score) > abs(prev.score):
                aspects[aspect] = AspectVerdict(
                    aspect=aspect,
                    sentiment=_label(score),
                    score=round(score, 3),
                    evidence=clause[:160],
                )

    return ABSAResult(
        overall_sentiment=_label(overall),
        overall_score=round(overall, 3),
        aspects=sorted(aspects.values(), key=lambda a: a.score),
        has_serious_cue=has_serious_cue(text),
        has_detail=bool(DETAIL_CUES.search(text)),
        word_count=word_count,
        is_gibberish=False,
    )


def to_dict(result: ABSAResult) -> dict:
    return {
        "overall_sentiment": result.overall_sentiment,
        "overall_score": result.overall_score,
        "has_serious_cue": result.has_serious_cue,
        "has_detail": result.has_detail,
        "word_count": result.word_count,
        "is_gibberish": result.is_gibberish,
        "aspects": [
            {"aspect": a.aspect, "sentiment": a.sentiment, "score": a.score, "evidence": a.evidence}
            for a in result.aspects
        ],
    }
