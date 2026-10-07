"""Aggregate insights read from MongoDB collections."""
from __future__ import annotations

from app.db import mongo


def build_insights(limit_recent: int = 20, offset: int = 0, store_id: str | None = None) -> dict:
    fb = mongo.feedback_collection()
    an = mongo.analysis_collection()
    tickets = mongo.tickets_collection()
    rewards = mongo.rewards_collection()

    fb_filter: dict = {"store_id": store_id} if store_id else {}

    total_feedback = fb.count_documents(fb_filter) if fb_filter else fb.estimated_document_count()

    cat_pipeline: list[dict] = []
    if store_id:
        cat_pipeline.append({"$lookup": {
            "from": "feedback", "localField": "submission_id",
            "foreignField": "submission_id", "as": "fb",
        }})
        cat_pipeline.append({"$match": {"fb.store_id": store_id}})
    cat_pipeline.append({"$group": {"_id": "$category", "count": {"$sum": 1}}})
    by_category = {row["_id"]: int(row["count"]) for row in an.aggregate(cat_pipeline)}

    by_store = {
        (row["_id"] or "unspecified"): int(row["count"])
        for row in fb.aggregate([{"$group": {"_id": "$store_id", "count": {"$sum": 1}}}])
    }

    ticket_filter = {"store_id": store_id} if store_id else {}
    status_counts = {
        row["_id"]: int(row["count"])
        for row in tickets.aggregate([
            {"$match": ticket_filter},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ])
    }
    eligible_filter = {"eligibility_checked": True, "eligible": True}
    issued_filter = {**eligible_filter, "status": "issued"}
    issued_amounts = list(rewards.aggregate([
        {"$match": issued_filter},
        {"$group": {"_id": None, "amount_gbp": {"$sum": "$amount_gbp"}}},
    ]))
    reward_total_gbp = round(float(issued_amounts[0]["amount_gbp"]), 2) if issued_amounts else 0.0
    reward_count = rewards.count_documents(issued_filter)

    recent = []
    pipeline: list[dict] = []
    if store_id:
        pipeline.append({"$match": {"store_id": store_id}})
    pipeline += [
        {"$sort": {"created_at": -1}},
        {"$skip": offset},
        {"$limit": limit_recent},
        {"$lookup": {
            "from": "analysis", "localField": "submission_id",
            "foreignField": "submission_id", "as": "analysis",
        }},
    ]
    for doc in fb.aggregate(pipeline):
        analysis = (doc.get("analysis") or [{}])[0]
        recent.append({
            "submission_id": doc.get("submission_id"),
            "customer_name": doc.get("name"),
            "customer_email": doc.get("email"),
            "sparks_member": doc.get("sparks_member"),
            "sparks_id": doc.get("sparks_id"),
            "store_id": doc.get("store_id"),
            "stars": doc.get("stars"),
            "text": doc.get("text", "")[:400],
            "created_at": doc.get("created_at"),
            "category": analysis.get("category"),
            "category_confidence": analysis.get("category_confidence"),
            "needs_review": analysis.get("needs_review"),
            "reward_tier": analysis.get("reward_tier"),
            "needs_ticket": analysis.get("needs_ticket"),
            "aspects": analysis.get("aspects") or [],
            "overall_sentiment": analysis.get("overall_sentiment"),
            "priority": analysis.get("priority"),
        })

    return {
        "total_feedback": total_feedback,
        "by_category": by_category,
        "by_store": by_store,
        "open_tickets": status_counts.get("open", 0) + status_counts.get("in_progress", 0),
        "resolved_tickets": status_counts.get("resolved", 0),
        "total_rewards_issued": reward_count,
        "total_gbp_issued": reward_total_gbp,
        "has_more_recent": offset + len(recent) < total_feedback,
        "recent": recent,
    }
