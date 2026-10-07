"""Read-only description of MongoDB storage and submission flow."""
from __future__ import annotations

from fastapi.encoders import jsonable_encoder

from app.config import BACKEND_ROOT, settings
from app.db import mongo


COLLECTIONS = [
    ("feedback", "What the customer wrote: name, email, store, stars, text, Sparks number"),
    ("customer_emails", "Simulated generic acknowledgement and one-time reward-eligibility follow-up"),
    ("analysis", "The analyser's decision, confidence, reply and trace"),
    ("rewards", "Reward recommendations and colleague decisions"),
    ("reward_eligibility", "Store colleague's final eligible/not-eligible choice and selected tier"),
    ("tickets", "Open, in-progress and resolved issues raised from feedback"),
    ("ticket_events", "Ticket history: who changed what and when"),
    ("staff_users", "Colleague credentials with Argon2 password hashes"),
    ("staff_sessions", "Hashed session tokens with expiry"),
]


def _file_info(label: str, rel: str, count_rows: bool = False) -> dict:
    path = BACKEND_ROOT / rel
    info: dict = {"label": label, "path": f"backend/{rel}", "exists": path.exists()}
    if path.exists():
        info["size_mb"] = round(path.stat().st_size / 1_048_576, 2)
        if count_rows:
            with path.open("rb") as f:
                info["rows"] = max(sum(1 for _ in f) - 1, 0)
    return info


def overview() -> dict:
    mongo_ok = True
    collections = []
    try:
        mongo.client().admin.command("ping")
        for name, holds in COLLECTIONS:
            collections.append({"name": name, "holds": holds, "count": mongo.database()[name].count_documents({})})
    except Exception:
        mongo_ok = False

    recent: list[dict] = []
    if mongo_ok:
        for doc in mongo.feedback_collection().find(
            {}, {"submission_id": 1, "name": 1, "text": 1, "created_at": 1},
        ).sort("created_at", -1).limit(15):
            recent.append({"submission_id": doc["submission_id"], "name": doc.get("name"),
                           "text": (doc.get("text") or "")[:90], "created_at": doc.get("created_at")})

    return jsonable_encoder({
        "mongodb": {
            "ok": mongo_ok,
            "database": settings.mongodb_database,
            "host": settings.mongodb_uri.split("@")[-1],
            "collections": collections,
        },
        "files": [
            _file_info("Training dataset (synthetic)", "data/retail_feedback.csv", count_rows=True),
            _file_info("Trained model", "data/absa_models.joblib"),
            _file_info("Model scores", "data/absa_metrics.json"),
            _file_info("Analyser settings", "policy.json"),
        ],
        "model": {"backend": settings.llm_backend},
        "recent": recent,
    })


def follow(submission_id: str) -> dict | None:
    fb = mongo.feedback_collection().find_one({"submission_id": submission_id}, {"_id": 0})
    if fb is None:
        return None
    analysis = mongo.analysis_collection().find_one({"submission_id": submission_id}, {"_id": 0})
    ticket = mongo.tickets_collection().find_one({"submission_id": submission_id}, {"_id": 0})
    reward = mongo.rewards_collection().find_one({"submission_id": submission_id}, {"_id": 0})
    eligibility = mongo.reward_eligibility_collection().find_one(
        {"submission_id": submission_id}, {"_id": 0},
    )
    messages = list(mongo.customer_emails_collection().find(
        {"submission_id": submission_id}, {"_id": 0},
    ).sort("created_at", 1))
    events = [] if ticket is None else list(mongo.ticket_events_collection().find(
        {"ticket_id": ticket["id"]}, {"_id": 0},
    ).sort("created_at", 1))

    steps = [
        {"order": 1, "store": "MongoDB", "location": f"{settings.mongodb_database}.feedback", "what": "Saved first, exactly as the customer sent it", "record": fb},
        {"order": 2, "store": "MongoDB", "location": f"{settings.mongodb_database}.customer_emails", "what": "Same generic acknowledgement for every submission, then one eligibility follow-up when applicable; simulated, not delivered", "record": messages or None},
        {"order": 3, "store": "MongoDB", "location": f"{settings.mongodb_database}.analysis", "what": "The analyser's decision and trace, saved with the same submission id", "record": analysis},
        {"order": 4, "store": "MongoDB", "location": f"{settings.mongodb_database}.reward_eligibility", "what": "Store colleague's final eligibility and tier decision; only eligible feedback enters Rewards", "record": eligibility},
        {"order": 5, "store": "MongoDB", "location": f"{settings.mongodb_database}.rewards", "what": "Incentive issued after a colleague confirms eligibility", "record": reward,
         "absent": "No reward was recommended for this feedback"},
        {"order": 6, "store": "MongoDB", "location": f"{settings.mongodb_database}.tickets", "what": "Ticket opened automatically when the feedback needed action", "record": ticket,
         "absent": "No ticket was needed for this feedback"},
        {"order": 7, "store": "MongoDB", "location": f"{settings.mongodb_database}.ticket_events", "what": "Audit trail for the ticket", "record": events or None,
         "absent": "No ticket, so no events"},
    ]
    return jsonable_encoder({"submission_id": submission_id, "steps": steps})
