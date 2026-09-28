import re
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS


SUBJECT = re.compile(
    r"\b(?:baby clothes|clothes|jeans?|shirts?|t-shirt|jacket|zipper|shoes?|dress|"
    r"food|meal|milk|bread|bakery|cakes?|cookies?|sandwich(?:es)?|packaging|products?|items?|"
    r"refund|payment|card|account|checkout|till|order|delivery|manager|staff|"
    r"colleague|employee|service|store|aisle|ramp|wheelchair|lighting|fitting room|"
    r"shelf|shelves|labels?|signs?|signage|entrance|receipts?|prices?|sizes?|lock)\b"
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
USEFUL_DETAIL = re.compile(
    r"\b(?:after|before|during|when|by|every|often|always|yesterday|today|"
    r"lunchtime|evening|morning|minutes?|hours?|days?|weeks?|wash well|"
    r"resolved|replaced|replacement|helped|found|finding|arranging|"
    r"stayed soft|kept their shape|poppers|seams?|lining|zipper|lock|"
    r"eye strain|charged twice|could not|couldn't|unable to)\b"
)
POSITIVE_DETAIL = re.compile(
    r"\b(?:wash well|stayed soft|kept their shape|resolved|replaced|replacement|"
    r"helped|found|finding|arranging|explained|lasted|fits? well|fasten securely)\b"
)
IMPROVEMENT = re.compile(r"\b(?:please|could you|should|suggest|recommend|would help|would be helpful)\b")
ACTION = re.compile(r"\b(?:add|move|display|label|provide|repair|replace|improve|install|restock|replenish|stock|open|update)\b")


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
    useful = has_details and model_genuine and subject and len(content_words) >= 3 and bool(USEFUL_DETAIL.search(text))
    suggestion = (has_details and subject and len(content_words) >= 6 and
                  observed(IMPROVEMENT, text) and observed(ACTION, text) and
                  bool(re.search(r"\b(?:so|because|to help|near|beside|at|on|before|after|during)\b", text)))
    positive_detail = observed(POSITIVE_DETAIL, text)
    ticket_required = False
    tier = "none"

    if serious or unresolved_financial:
        category = "serious_complaint"
        decision = "eligible" if detailed else "pending"
        ticket_required = True
        tier = "tier_based" if detailed else "none"
        response = "We're sincerely sorry to hear about this. This issue requires priority attention from the store."
        reason = (
            "A serious complaint identifies the product or service and describes an impact; eligible under the complaint policy."
            if detailed else
            "Awaiting customer details before the automatic incentive decision. The issue still requires priority attention."
        )
    elif complaint and (subject or has_details):
        category = "minor_complaint"
        decision = "eligible" if useful else "not_eligible"
        tier = "tier_based" if useful else "none"
        ticket_required = has_details and subject and len(content_words) >= 3
        response = "We're sorry your experience did not meet expectations. Thank you for bringing this to our attention."
        reason = ("Specific feedback identifies a store problem with useful context for follow-up; eligible regardless of sentiment."
              if useful else "The complaint needs more specific, useful context before an incentive can be recommended.")
        if not ticket_required:
            response += " Please share which product or service was involved and what happened so we can open a ticket."
            reason = "More details are needed before opening a minor-complaint ticket."
    elif suggestion:
        category = "suggestion"
        decision = "eligible" if model_genuine else "pending"
        tier = "tier_based" if model_genuine else "none"
        response = "Thank you for suggesting a specific improvement for the store."
        reason = ("The suggestion identifies a concrete change and its location or benefit; eligible regardless of sentiment."
                  if model_genuine else "Please add an observed example so the usefulness of this suggestion can be assessed.")
    elif observed(EXCEPTIONAL_SERVICE, text) and has_details and model_genuine and subject and len(content_words) >= 8:
        category = "major_compliment"
        decision = "eligible"
        tier = "tier_based"
        response = "Thank you for sharing how our team made a difference. We appreciate your detailed recognition."
        reason = "Detailed recognition of exceptional service qualifies for a tier-based incentive recommendation."
    elif observed(PRAISE, text) or positive_detail:
        category = "compliment"
        decision = "eligible" if useful and positive_detail else "not_eligible"
        tier = "tier_based" if decision == "eligible" else "none"
        praised_subject = SUBJECT.search(text)
        response = f"Thank you for your kind feedback about our {praised_subject.group()}." if praised_subject else "Thank you for your kind feedback."
        reason = ("Specific positive feedback describes what worked well and helps the store recognise or repeat it; eligible regardless of sentiment."
              if decision == "eligible" else "General praise is acknowledged, but a specific useful example is needed for an incentive.")
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

    needs_details = decision == "pending"
    if loyal_customer and model_genuine and has_details and category != "ignored":
        decision = "eligible"
        tier = "high"
        reason = "Genuine feedback from a loyal customer qualifies for a high-tier incentive recommendation. Points amounts are not configured."

    questions = []
    if needs_details or (category == "minor_complaint" and not ticket_required):
        if not subject:
            questions.append("Which product or service was involved?")
        if not has_details or len(content_words) < 5 or category == "needs_clarification":
            questions.append("What happened during your visit or purchase?")
        if category == "serious_complaint" and not impact:
            questions.append("How did the issue affect you?")
        if not questions:
            questions.append("When did this happen, and what specific problem did you encounter?")
        response += " " + " ".join(questions)

    return {
        "category": category,
        "rewardDecision": decision,
        "rewardEligible": decision == "eligible",
        "customerResponse": response,
        "reason": reason,
        "ticketRequired": ticket_required,
        "incentiveTier": tier,
        "clarificationQuestions": questions,
    }