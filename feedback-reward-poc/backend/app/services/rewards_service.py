"""Manual eligibility decisions and issued reward records."""
from __future__ import annotations

from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from app.db import mongo
from app.services.customer_emails import record_simulated_email
from app.services.rewards import pounds_for


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def decide_eligibility(submission_id: str, *, actor: str, tier: str, note: str | None = None) -> dict | None:
    if tier not in {"none", "low", "mid", "high"}:
        raise ValueError("Choose not eligible or a valid reward tier.")
    feedback = mongo.feedback_collection().find_one({"submission_id": submission_id})
    analysis = mongo.analysis_collection().find_one({"submission_id": submission_id}, {"_id": 0})
    if feedback is None or analysis is None:
        return None

    eligible = tier != "none"
    decision_collection = mongo.reward_eligibility_collection()
    decision = {
        "submission_id": submission_id,
        "suggested_tier": analysis.get("reward_tier", "none"),
        "suggested_amount_gbp": float(pounds_for(analysis.get("reward_tier", "none"))),
        "tier": tier,
        "eligible": eligible,
        "decided_by": actor,
        "decided_at": _utcnow(),
        "note": note or None,
    }
    existing_decision = decision_collection.find_one({"submission_id": submission_id}, {"_id": 0})
    if existing_decision and (existing_decision.get("tier") != tier or existing_decision.get("note") != (note or None)):
        raise ValueError("Eligibility was already decided for this feedback.")
    rewards = mongo.rewards_collection()
    existing_reward = rewards.find_one({"submission_id": submission_id}, {"_id": 0})
    existing_followup = mongo.customer_emails_collection().find_one({
        "submission_id": submission_id, "kind": "reward_eligibility",
    }, {"_id": 1})
    if existing_decision and (not eligible or (existing_reward and existing_reward.get("status") == "issued" and existing_followup)):
        return existing_decision
    if existing_decision is None:
        try:
            decision_collection.insert_one(decision)
        except DuplicateKeyError:
            existing_decision = decision_collection.find_one({"submission_id": submission_id}, {"_id": 0})
            if existing_decision is None or existing_decision.get("tier") != tier or existing_decision.get("note") != (note or None):
                raise ValueError("Eligibility was already decided for this feedback.")
            decision = existing_decision
    else:
        decision = existing_decision

    if not eligible:
        if existing_reward:
            rewards.update_one(
                {"submission_id": submission_id},
                {"$set": {"eligibility_checked": True, "eligible": False}},
            )
        mongo.analysis_collection().update_one(
            {"submission_id": submission_id}, {"$set": {"reward_followup": None}},
        )
        return decision

    amount_gbp = float(pounds_for(tier))
    now = _utcnow()
    if existing_reward and existing_reward.get("status") != "issued":
        rewards.update_one(
            {"submission_id": submission_id},
            {"$push": {"decision_history": {
                "status": existing_reward.get("status"),
                "decided_by": existing_reward.get("decided_by"),
                "decided_at": existing_reward.get("decided_at"),
                "decision_note": existing_reward.get("decision_note"),
            }}},
        )
    reward_update = {
        "$set": {
            "tier": tier,
            "amount_gbp": amount_gbp,
            "status": "issued",
            "eligibility_checked": True,
            "eligible": True,
            "decided_by": actor,
            "decided_at": decision["decided_at"],
            "decision_note": decision.get("note"),
            "eligibility_decided_by": actor,
            "eligibility_decided_at": decision["decided_at"],
        },
    }
    if existing_reward is None:
        reward_update["$setOnInsert"] = {
                "id": mongo.next_id("reward"),
                "submission_id": submission_id,
                "customer_email": feedback.get("email"),
                "issued_at": now,
            }
    rewards.update_one({"submission_id": submission_id}, reward_update, upsert=True)
    subject = "An update on your feedback"
    content = (
        f"A store colleague reviewed your feedback and confirmed that you are eligible for a £{amount_gbp:.2f} "
        f"{tier.title()}-tier incentive. The decision has been recorded in our system."
    )
    followup = record_simulated_email(submission_id, feedback["email"], "reward_eligibility", subject, content)
    mongo.analysis_collection().update_one(
        {"submission_id": submission_id},
        {"$set": {"reward_followup": followup["body"], "manual_reward_eligibility": decision}},
    )
    return decision


def list_rewards(*, limit: int = 100) -> list[dict]:
    query = {"eligibility_checked": True, "eligible": True, "status": "issued"}
    rows = list(mongo.rewards_collection().find(query, {"_id": 0}).sort("issued_at", -1).limit(limit))
    if not rows:
        return []

    submission_ids = [r["submission_id"] for r in rows]
    feedbacks = {
        d["submission_id"]: d
        for d in mongo.feedback_collection().find({"submission_id": {"$in": submission_ids}})
    }
    analyses = {
        d["submission_id"]: d
        for d in mongo.analysis_collection().find({"submission_id": {"$in": submission_ids}})
    }

    out: list[dict] = []
    for reward in rows:
        fb = feedbacks.get(reward["submission_id"], {})
        an = analyses.get(reward["submission_id"], {})
        out.append({
            "id": reward["id"],
            "submission_id": reward["submission_id"],
            "customer_email": reward.get("customer_email"),
            "customer_name": fb.get("name"),
            "store_id": fb.get("store_id"),
            "stars": fb.get("stars"),
            "sparks_member": fb.get("sparks_member"),
            "sparks_id": fb.get("sparks_id"),
            "feedback": fb.get("text"),
            "category": an.get("category"),
            "aspects": an.get("aspects") or [],
            "tier": reward["tier"],
            "amount_gbp": reward["amount_gbp"],
            "status": reward["status"],
            "decided_by": reward.get("decided_by") or reward.get("eligibility_decided_by"),
            "decided_at": reward.get("decided_at"),
            "decision_note": reward.get("decision_note"),
            "issued_at": reward["issued_at"],
        })
    return out
