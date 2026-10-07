"""Triage prompt + JSON schema the model MUST return.

Categories (what the business cares about):
- minor_compliment : thank with context; no ticket by default.
- gibberish        : incoherent, test, or spam text; ignore quietly.
- minor_complaint  : apologise and ask for details; open a ticket when actionable.
- serious_complaint: safety/legal/financial-impact or repeated unresolved issue.
                     Open and assign a high-priority ticket; apologise and offer high tier.
- major_compliment : thank the customer and offer mid tier.

Genuine feedback from a Sparks member receives high tier. Incentives are GBP
recommendations and require colleague approval before issue.
"""
from __future__ import annotations

from typing import Any

from app.llm.base import AIRequest, BaseAI

REWARD_TIERS_FOR_CATEGORY = {
   "minor_compliment": "none",
   "gibberish": "none",
   "minor_complaint": "none",
   "serious_complaint": "high",
   "major_compliment": "mid",
}

SYSTEM_PROMPT = """You are the Marks & Spencer customer-feedback triage assistant.

Classify a single piece of customer feedback and output JSON matching the schema.

Rules:
1. category must be one of:
   - "minor_compliment" : brief positive but generic (e.g. "nice staff", "liked it").
   - "gibberish"        : nonsense, test strings, random characters, spam, empty intent.
   - "minor_complaint"  : small, non-safety issue (e.g. "shelf a bit messy").
   - "serious_complaint": safety, allergen, injury, discrimination, theft, fraud,
     unauthorised charge, repeated unresolved issue over weeks, or anything with
     clear harm or legal/financial impact.
   - "major_compliment" : specific, strongly positive feedback naming a product,
     colleague, store experience, or outcome that went above and beyond.

2. genuine = true only if the text looks like real feedback from a real visit
   (specific detail, consistent intent). Gibberish is never genuine.

3. has_sufficient_detail = true only if ALL of these hold: it names a specific
   product or service; it says what was good or went wrong; it is at least 8
   words; and it gives a specific (when, where, who or what). Vague "it was
   bad" / "nice store" = false.

4. needs_ticket = true if category == "serious_complaint", OR
   (category == "minor_complaint" AND has_sufficient_detail).

5. priority:
   - "high"   for serious_complaint with safety/legal/financial impact.
   - "medium" for serious_complaint without immediate harm, or escalating minor_complaint.
   - "low"    for everything else that opens a ticket.
   - Still output a priority even if needs_ticket is false (use "low").

6. reward_tier:
   - "high" for genuine serious_complaint feedback.
   - "mid" for genuine major_compliment feedback.
   - "high" for any genuine feedback from a Sparks member.
   - "none" otherwise, and ALWAYS "none" if genuine is false or category is gibberish.
   Reward eligibility does not depend on the four-check detail assessment.
   A store colleague makes the final eligibility decision; eligible incentives are recorded as issued.

7. customer_reply: 2-4 short sentences, warm, M&S tone, no emoji, no promises of
   fixed outcomes. If needs_ticket, mention someone will follow up. If reward_tier
   is not none, say the pound-denominated recommendation is pending colleague
   approval. Never claim a reward is already issued, or claim a real refund, voucher, or that a human has
   already been contacted.

8. staff_summary: one short sentence (max 25 words) describing the issue or
   praise for a colleague queue card.

Output ONLY the JSON object required by the schema. No extra text.
"""


TRIAGE_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "category", "genuine", "has_sufficient_detail", "reward_tier",
        "needs_ticket", "priority", "customer_reply", "staff_summary",
    ],
    "properties": {
        "category": {
            "type": "string",
            "enum": ["minor_compliment", "gibberish", "minor_complaint",
                     "serious_complaint", "major_compliment"],
        },
        "genuine": {"type": "boolean"},
        "has_sufficient_detail": {"type": "boolean"},
        "reward_tier": {"type": "string", "enum": ["none", "low", "mid", "high"]},
        "needs_ticket": {"type": "boolean"},
        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
        "customer_reply": {"type": "string", "maxLength": 600},
        "staff_summary": {"type": "string", "maxLength": 240},
    },
}


def enforce_rules(result: dict[str, Any]) -> tuple[bool, list[str]]:
   category = result["category"]
   detail = result.get("detail")
   detailed = bool(detail["detailed"]) if detail else bool(result.get("has_sufficient_detail"))
   missing = list(detail["missing"]) if detail else ([] if detailed else ["specifics"])
   genuine = bool(result.get("genuine", False)) and category != "gibberish"
   loyal = bool(result.get("sparks_member", False))
   result["genuine"] = genuine
   result["has_sufficient_detail"] = detailed
   if genuine and loyal:
      reward_tier = "high"
   elif genuine and category in ("serious_complaint", "major_compliment"):
      reward_tier = REWARD_TIERS_FOR_CATEGORY[category]
   else:
      reward_tier = "none"
   result["reward_tier"] = reward_tier
   result["needs_ticket"] = category == "serious_complaint" or (category == "minor_complaint" and detailed)
   result["priority"] = "high" if category == "serious_complaint" else (
      "medium" if result["needs_ticket"] else "low"
   )
   trace = result.get("trace")
   if trace is not None:
      trace.setdefault("reward", {})["tier"] = result["reward_tier"]
      trace.setdefault("ticket", {})["opened"] = result["needs_ticket"]
      trace["review_flag"] = bool(result.get("needs_review"))
      if reward_tier == "high" and loyal:
         trace["reward"]["reason"] = "Genuine feedback from a Sparks member qualifies for the high tier"
      elif reward_tier == "high":
         trace["reward"]["reason"] = "Genuine serious complaint qualifies for the high tier"
      elif reward_tier == "mid":
         trace["reward"]["reason"] = "Genuine major compliment qualifies for the mid tier"
      elif category == "minor_complaint":
         trace["reward"]["reason"] = "No incentive for a minor complaint unless the customer is a loyal Sparks member"
      else:
         trace["reward"]["reason"] = "No reward recommended under the feedback policy"
   return detailed, missing


def triage(ai: BaseAI, feedback: str, stars: int, store_id: str, sparks_member: bool = False) -> dict | None:
   req = AIRequest(
      task="triage",
      system=SYSTEM_PROMPT,
      payload={"feedback": feedback, "stars": stars, "store_id": store_id, "sparks_member": sparks_member},
      schema=TRIAGE_SCHEMA,
   )
   result = ai.ask(req)
   if result is not None:
      result["sparks_member"] = sparks_member
      enforce_rules(result)
   return result
