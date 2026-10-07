"""Record simulated customer emails once per submission and message type."""
from __future__ import annotations

from datetime import datetime, timezone

from app.db import mongo

GENERIC_ACK_SUBJECT = "We've received your feedback"
GENERIC_ACK_CONTENT = (
    "Thank you for sharing your feedback with M&S. We have received it and appreciate you taking the time to get in touch. "
    "Our team will review it and contact you if more information is needed."
)


def format_email(subject: str, content: str) -> str:
    return f"Subject: {subject}\n\nHello,\n\n{content}\n\nKind regards,\nM&S Customer Care"


def record_simulated_email(submission_id: str, to: str, kind: str, subject: str, content: str) -> dict:
    record_id = f"{submission_id}:{kind}"
    collection = mongo.customer_emails_collection()
    collection.update_one(
        {"_id": record_id},
        {"$setOnInsert": {
            "submission_id": submission_id,
            "kind": kind,
            "to": to,
            "subject": subject,
            "body": format_email(subject, content),
            "delivery_mode": "in_app_simulation",
            "status": "simulated",
            "created_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return collection.find_one({"_id": record_id}, {"_id": 0}) or {}