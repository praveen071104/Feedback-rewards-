"""Customer-facing replies: plain, warm and British, and never promising more than really happens."""
from __future__ import annotations

import re

LABEL = {
    "product_quality": "the product",
    "availability": "stock and sizes",
    "staff_service": "our colleagues",
    "checkout_payment": "the checkout",
    "delivery_online": "your delivery",
    "returns_refund": "your return or refund",
    "store_environment": "the store",
    "price_value": "our prices",
    "accessibility": "access in store",
    "online_app": "our app or website",
    "loyalty_sparks": "Sparks",
    "gifting": "our gifting",
}

ASK = {
    "subject": "which product or service you mean",
    "opinion": "what exactly went wrong, or went well",
    "length": "a little more about what happened",
    "specifics": "when and where it happened, or who helped you",
}

_HEALTH = re.compile(
    r"\b(allerg\w*|reaction|poison\w*|injur\w*|hospital\w*|doctor|sick|unwell|glass|stitches|slipped|fell)\b",
    re.IGNORECASE,
)


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _topics(aspects: list[dict], sentiment: str) -> str:
    seen: list[str] = []
    for a in aspects:
        label = LABEL.get(a.get("aspect", ""))
        if a.get("sentiment") == sentiment and label and label not in seen:
            seen.append(label)
    return _join(seen[:2])


def _first(name: str | None) -> str | None:
    token = (name or "").strip().split(" ")[0]
    return token[:1].upper() + token[1:] if token else None


def _reward_line(amount_gbp: float | None) -> str:
    if amount_gbp is None:
        return "A pound-denominated incentive has been suggested for a colleague to review."
    return f"A £{amount_gbp:.2f} incentive has been suggested for a colleague to review."


def compose(
    *,
    category: str,
    text: str,
    aspects: list[dict],
    detailed: bool,
    missing: list[str],
    needs_ticket: bool,
    reward_tier: str,
    ticket_ref: int | None = None,
    first_name: str | None = None,
    sparks_member: bool = False,
    reward_amount_gbp: float | None = None,
) -> str:
    name = _first(first_name)
    good, bad = _topics(aspects, "positive"), _topics(aspects, "negative")
    ask = _join([ASK[m] for m in missing if m in ASK])
    ref = f" Your reference is #{ticket_ref}." if ticket_ref else ""
    paras: list[str] = []

    if category == "gibberish":
        paras.append("We couldn't identify actionable feedback in this message, so no case has been raised.")

    elif category == "minor_compliment":
        paras.append(f"Thank you for your kind words{f' about {good}' if good else ''}. We're glad you had "
                 "a good experience. Your feedback has been recorded so the team can see what went well.")
        if bad:
            paras.append(f"We're sorry to hear that {bad} wasn't quite right. We've noted it so the team can look at it.")

    elif category == "major_compliment":
        paras.append(f"Thank you so much for such lovely feedback{f' about {good}' if good else ''}. "
                 "We appreciate you taking the time to share it.")
        if reward_tier != "none":
            paras.append(_reward_line(reward_amount_gbp))
        elif ask:
            paras.append(f"If you have a moment, telling us {ask} helps us recognise the right people.")

    elif category == "minor_complaint":
        # Several different topics in one complaint read better as "what you've described".
        tell = f"telling us about {bad}" if bad and " and " not in bad else "telling us what happened"
        sorry = "we're sorry it wasn't up to the standard you expect from M&S."
        if good and good == bad:
            opener = f"Thank you for your feedback. We're glad part of it went well, and {sorry}"
        elif good:
            opener = f"We're glad you enjoyed {good}. Thank you for {tell}, and {sorry}"
        else:
            opener = f"Thank you for {tell}, and {sorry}"
        paras.append(opener)
        if needs_ticket:
            paras.append(f"Your feedback has been recorded for our team to review.{ref}")
        else:
            paras.append(f"We've recorded this feedback but haven't opened a ticket yet. To help us look into it, "
                         f"could you tell us {ask}?" if ask else
                         "We've noted your feedback; no ticket was needed.")
        if reward_tier != "none":
            paras.append(_reward_line(reward_amount_gbp))

    elif category == "serious_complaint":
        paras.append("We're so sorry. This isn't the experience we want for any customer, and we take what you've "
                     "described very seriously.")
        if _HEALTH.search(text or ""):
            paras.append("If you or anyone else is unwell, please seek medical advice first.")
        paras.append(f"Your concern has been recorded as a high-priority case and assigned to our Customer Care team. "
                 f"We've included the contact details you provided so they can follow up.{ref}")
        keep = "If you still have the product, packaging or receipt, please keep hold of them."
        if not detailed and ask:
            paras.append(f"So we can act as quickly as possible, please send us another message telling us {ask}. {keep}")
        else:
            paras.append(keep)
        if reward_tier != "none":
            paras.append(_reward_line(reward_amount_gbp))

    return "\n\n".join([f"Dear {name}," if name else "Hello,", *paras, "Kind regards,\nM&S Customer Care"])
