import re
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS


SUBJECT = re.compile(
    r"\b(?:baby clothes|clothes|jeans?|shirts?|t-shirt|jacket|zipper|shoes?|dress|"
    r"food|meal|milk|bread|bakery|cakes?|cookies?|sandwich(?:es)?|packaging|products?|items?|"
    r"refund|payment|card|account|checkout|till|order|delivery|manager|staff|"
    r"colleague|employee|service|store|aisle|ramp|wheelchair|lighting|fitting room)\b"
)
COMPLAINT = re.compile(
    r"\b(?:complaint|broken|broke|faulty|damaged|rude|slow|dirty|cold|stale|"
    r"queue|queues|waiting|waited|delay|delayed|missing|unavailable|unavailability|"
    r"sold\s*out|out of stock|no stock|restock\w*|not available|too dim|eye strain|"
    r"froze|failed|failure|overcharged|ignored|unhelpful|disappointed|unsafe|"
    r"not arrived|did not arrive|hasn't arrived|never arrived|nobody replies|"
    r"no response|no reply|not get a proper response|not receive|not received)\b"
)
SERIOUS = re.compile(
    r"\b(?:food poisoning|allergic reaction|hospital\w*|injur\w*|burned|burnt|"
    r"choking|choked|glass|mould\w*|mold\w*|unsafe|discriminat\w*|harass\w*|"
    r"racis\w*|threaten\w*|overcharged|charged twice|double charged|"
    r"unauthori[sz]ed charge|blocked|inaccessible|eye strain)\b"
)
IMPACT = re.compile(
    r"\b(?:food poisoning|allergic reaction|hospital\w*|injur\w*|burned|burnt|"
    r"chok\w*|cut my|cut his|cut her|became ill|made me ill|vomit\w*|"
    r"charged twice|double charged|overcharged|unauthori[sz]ed charge|"
    r"could not enter|couldn't enter|could not access|couldn't access|"
    r"unable to enter|unable to access|eye strain|lost money|out of pocket|"
    r"still waiting|not arrived|hasn't arrived|not received|no refund|"
    r"nobody replies|no response|no reply|ignored|discriminat\w*|harass\w*)\b"
)
REPEATED = re.compile(r"\b(?:weeks?|months?|repeatedly|several times|multiple times)\b")
FINANCIAL = re.compile(r"\b(?:refund|payment|money|charge|charged)\b")
PRAISE = re.compile(
    r"\b(?:lovely|love|good|great|excellent|helpful|thank\w*|nice|wonderful|"
    r"amazing|perfect|wash well|resolved|replacement)\b"
)
NEGATION = re.compile(r"\b(?:not|never|no|wasn't|wasnt|isn't|isnt|weren't|without)\s+(?:\w+\s+){0,2}$")
HYPOTHETICAL = re.compile(r"\b(?:if|might|could cause|could lead|could result|worried about|risk of|prevent)\b")
EXCEPTIONAL_SERVICE = re.compile(r"\b(?:above and beyond|exceptional|outstanding|went out of (?:their|her|his) way)\b")
SERVICE_RECOVERY = re.compile(r"\b(?:resolved|fixed|replaced|finding my missing order|found my missing order)\b")


def observed(pattern: re.Pattern, text: str) -> bool:
    return any(not NEGATION.search(text[:match.start()]) for match in pattern.finditer(text))


def triage_feedback(feedback: str, has_details: bool, model_genuine: bool = True, loyal_customer: bool = False) -> dict:
    text = feedback.lower().replace("\u2019", "'")
    clauses = re.split(r"[.!?;\n]|\bbut\b|\bhowever\b", text)
    observed_clauses = [clause for clause in clauses if not HYPOTHETICAL.search(clause)]
    serious = any(observed(SERIOUS, clause) for clause in clauses)
    impact = any(observed(IMPACT, clause) for clause in observed_clauses)
    unresolved_financial = bool(FINANCIAL.search(text) and REPEATED.search(text) and impact)
    complaint = serious or unresolved_financial or any(
        observed(COMPLAINT, clause) and not (
            observed(EXCEPTIONAL_SERVICE, clause) and observed(SERVICE_RECOVERY, clause)
        ) for clause in clauses
    )
    subject = bool(SUBJECT.search(text))
    content_words = set(re.findall(r"[a-z]+", text)) - ENGLISH_STOP_WORDS
    detailed = has_details and subject and impact and len(content_words) >= 5
    ticket_required = False
    tier = "none"

    if serious or unresolved_financial:
        category = "serious_complaint"
        decision = "eligible" if detailed else "pending"
        ticket_required = True
        tier = "tier_based" if detailed else "none"
        response = "We're sorry to hear about this. Your complaint has been flagged for priority review."
        reason = (
            "A serious complaint identifies the product or service and describes an impact; eligible under the complaint policy."
            if detailed else
            "A potentially serious issue needs review. Please clarify the product or service, what happened and its impact."
        )
    elif complaint and (subject or has_details):
        category = "minor_complaint"
        decision = "not_eligible"
        ticket_required = has_details and subject and len(content_words) >= 3
        response = "We're sorry your experience did not meet expectations. Thank you for bringing this to our attention."
        reason = "A minor complaint needs follow-up; no incentive is recommended unless the customer is loyal and the feedback is genuine."
        if not ticket_required:
            response += " Please share which product or service was involved and what happened so we can open a ticket."
            reason = "More details are needed before opening a minor-complaint ticket."
    elif observed(EXCEPTIONAL_SERVICE, text) and has_details and model_genuine and subject and len(content_words) >= 8:
        category = "major_compliment"
        decision = "eligible"
        tier = "tier_based"
        response = "Thank you for sharing how our team made a difference. We appreciate your detailed recognition."
        reason = "Detailed recognition of exceptional service qualifies for a tier-based incentive recommendation."
    elif observed(PRAISE, text):
        category = "compliment"
        decision = "not_eligible"
        praised_subject = SUBJECT.search(text)
        response = f"Thank you for your kind feedback about our {praised_subject.group()}." if praised_subject else "Thank you for your kind feedback."
        reason = "A minor compliment is acknowledged and the loop is closed; no incentive is recommended."
    elif not has_details or not model_genuine:
        category = "ignored"
        decision = "not_eligible"
        response = ""
        reason = "No meaningful customer feedback was identified; no action or reward."
    else:
        category = "needs_clarification"
        decision = "pending"
        response = "Please tell us what happened, which product or service was involved, and how it affected you."
        reason = "The feedback is not clearly a compliment or complaint; clarification is needed before a reward decision."

    if loyal_customer and model_genuine and has_details and category not in {"ignored", "needs_clarification"}:
        decision = "eligible"
        tier = "high"
        reason = "A loyal customer provided genuine, specific feedback; a high-tier incentive is recommended."

    return {
        "category": category,
        "rewardDecision": decision,
        "rewardEligible": decision == "eligible",
        "customerResponse": response,
        "reason": reason,
        "ticketRequired": ticket_required,
        "incentiveTier": tier,
    }