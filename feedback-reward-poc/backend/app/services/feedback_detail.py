"""Full feedback detail lookup for the staff Insights drill-down."""
from __future__ import annotations

from app.db import mongo
from app.services.rewards import pounds_for


def feedback_detail(submission_id: str) -> dict | None:
    fb = mongo.feedback_collection().find_one({"submission_id": submission_id})
    if fb is None:
        return None
    an = mongo.analysis_collection().find_one({"submission_id": submission_id}) or {}
    eligibility = mongo.reward_eligibility_collection().find_one(
        {"submission_id": submission_id}, {"_id": 0},
    ) or {}

    ticket = mongo.tickets_collection().find_one({"submission_id": submission_id}, {"_id": 0})
    reward = mongo.rewards_collection().find_one({
        "submission_id": submission_id,
        "eligibility_checked": True,
        "eligible": True,
        "status": "issued",
    }, {"_id": 0})

    return {
        "submission_id": submission_id,
        "customer": {
            "name": fb.get("name"),
            "email": fb.get("email"),
            "phone": fb.get("phone"),
            "sparks_member": fb.get("sparks_member"),
            "sparks_id": fb.get("sparks_id"),
        },
        "store_id": fb.get("store_id"),
        "stars": fb.get("stars"),
        "text": fb.get("text"),
        "created_at": fb.get("created_at"),
        "reward_eligibility": {
            "suggested_tier": an.get("reward_tier", "none"),
            "suggested_amount_gbp": float(pounds_for(an.get("reward_tier", "none"))),
            "tier": eligibility.get("tier"),
            "eligible": eligibility.get("eligible"),
            "decided_by": eligibility.get("decided_by"),
            "decided_at": eligibility.get("decided_at"),
            "note": eligibility.get("note"),
        },
        "analysis": {
            "category": an.get("category"),
            "category_confidence": an.get("category_confidence"),
            "needs_review": an.get("needs_review"),
            "genuine": an.get("genuine"),
            "has_sufficient_detail": an.get("has_sufficient_detail"),
            "reward_tier": an.get("reward_tier"),
            "needs_ticket": an.get("needs_ticket"),
            "priority": an.get("priority"),
            "customer_reply": an.get("customer_reply"),
            "reward_followup": an.get("reward_followup"),
            "staff_summary": an.get("staff_summary"),
            "overall_sentiment": an.get("overall_sentiment"),
            "overall_score": an.get("overall_score"),
            "aspects": an.get("aspects") or [],
            "trace": an.get("trace"),
            "model": an.get("model"),
            "prompt_version": an.get("prompt_version"),
        },
        "ticket": None if ticket is None else {
            "id": ticket["id"],
            "status": ticket["status"],
            "priority": ticket["priority"],
            "assignee": ticket.get("assignee"),
            "opened_at": ticket["opened_at"],
            "closed_at": ticket.get("closed_at"),
            "resolution_notes": ticket.get("resolution_notes"),
        },
        "reward": None if reward is None else {
            "id": reward["id"],
            "tier": reward["tier"],
            "amount_gbp": reward["amount_gbp"],
            "status": reward["status"],
            "decided_by": reward.get("decided_by"),
            "decided_at": reward.get("decided_at"),
            "decision_note": reward.get("decision_note"),
            "issued_at": reward["issued_at"],
        },
    }
