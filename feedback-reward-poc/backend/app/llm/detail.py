"""Is there enough detail in a piece of feedback to act on it, or to reward it?

Four plain checks for actionable detail. Major compliments and serious complaint
reward recommendations require all four. Genuine minor complaints may receive a
low-tier recommendation while the customer is asked for missing detail.
"""
from __future__ import annotations

import re

_TIME = re.compile(
    r"\b(yesterday|today|tonight|this (?:morning|afternoon|evening|week|weekend)|"
    r"last (?:night|week|weekend|month|saturday|sunday|monday|tuesday|wednesday|thursday|friday)|"
    r"on (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"(?:\d+|an?|one|two|three|four|five|six|seven|eight|ten|fifteen|twenty|thirty|forty-five) "
    r"(?:minutes?|mins?|hours?|days?|weeks?|months?)|\d{1,2}(?::\d{2})? ?(?:am|pm)|for (?:weeks|days|months))\b",
    re.IGNORECASE,
)
_PLACE = re.compile(
    r"\b(tills?|checkout|self[- ]?(?:service|checkout)|aisle|food hall|caf[e\u00e9]|fitting rooms?|"
    r"returns? desk|bakery|entrance|car park|customer service|marble arch|stratford|bluewater|"
    r"oxford street|click (?:&|and) collect|collection point)\b",
    re.IGNORECASE,
)
_ITEM = re.compile(
    r"\b(per una|autograph|jaeger|goodmove|percy pigs?|colin|dine in|sparks wallet|dress(?:es)?|jeans|shirt|"
    r"jacket|trousers|cardigan|jumper|coat|blouse|shoes|skirt|sandwich|cake|bread|milk|chicken|salad|"
    r"biscuits|yogurt|ham|strawberries|ready meal|dessert|fruit|flowers|hamper|gift card)\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\u00a3\s?\d|\b\d{2,}\b|\bsize \d+\b", re.IGNORECASE)
_PERSON = re.compile(
    r"\b(?:colleague|assistant|manager|cashier|named|called)\s+[A-Z][a-z]{2,}|"
    r"\b[A-Z][a-z]{2,} (?:at|from|on) the (?:till|checkout|counter|bakery|caf[e\u00e9]|returns)"
)

MIN_WORDS = 8


def assess(text: str, aspects: list[dict], serious_cue: bool = False) -> dict:
    words = re.findall(r"[A-Za-z0-9\u00a3']+", text or "")
    specific = any(p.search(text or "") for p in (_TIME, _PLACE, _ITEM, _NUMBER, _PERSON))
    checks = [
        {"key": "subject", "label": "Names a product or service", "met": bool(aspects)},
        {"key": "opinion", "label": "Says what was good or went wrong",
         "met": bool(serious_cue) or any(a.get("sentiment") != "neutral" for a in aspects)},
        {"key": "length", "label": f"Gives enough to go on ({MIN_WORDS}+ words)", "met": len(words) >= MIN_WORDS},
        {"key": "specifics", "label": "Gives a specific: when, where, who or what", "met": specific},
    ]
    met = sum(c["met"] for c in checks)
    return {
        "detailed": met == len(checks),
        "level": "detailed" if met == len(checks) else ("some" if met >= 2 else "vague"),
        "checks": checks,
        "missing": [c["key"] for c in checks if not c["met"]],
    }
