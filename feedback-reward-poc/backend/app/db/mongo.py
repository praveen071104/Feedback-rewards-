"""MongoDB client + collection accessors with first-run index creation."""
from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database

from app.config import settings


_client: MongoClient | None = None


def client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000, uuidRepresentation="standard")
    return _client


def database() -> Database:
    return client()[settings.mongodb_database]


def feedback_collection() -> Collection:
    return database()["feedback"]


def analysis_collection() -> Collection:
    return database()["analysis"]


def staff_users_collection() -> Collection:
    return database()["staff_users"]


def staff_sessions_collection() -> Collection:
    return database()["staff_sessions"]


def tickets_collection() -> Collection:
    return database()["tickets"]


def ticket_events_collection() -> Collection:
    return database()["ticket_events"]


def rewards_collection() -> Collection:
    return database()["rewards"]


def customer_emails_collection() -> Collection:
    return database()["customer_emails"]


def reward_eligibility_collection() -> Collection:
    return database()["reward_eligibility"]


def next_id(name: str) -> int:
    counter = database()["counters"].find_one_and_update(
        {"_id": name}, {"$inc": {"value": 1}}, upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(counter["value"])


def ensure_indexes() -> None:
    fb = feedback_collection()
    fb.create_index([("submission_id", ASCENDING)], unique=True, name="uq_submission_id")
    fb.create_index([("created_at", DESCENDING)], name="created_at_desc")
    fb.create_index([("store_id", ASCENDING), ("created_at", DESCENDING)], name="store_recent")

    an = analysis_collection()
    an.create_index([("submission_id", ASCENDING)], unique=True, name="uq_submission_id")
    an.create_index([("category", ASCENDING), ("created_at", DESCENDING)], name="category_recent")

    users = staff_users_collection()
    users.create_index([("username", ASCENDING)], unique=True, name="uq_staff_username")

    sessions = staff_sessions_collection()
    sessions.create_index([("token_hash", ASCENDING)], unique=True, name="uq_session_token_hash")
    sessions.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0, name="expire_staff_sessions")

    tickets = tickets_collection()
    tickets.create_index([("id", ASCENDING)], unique=True, name="uq_ticket_id")
    tickets.create_index([("submission_id", ASCENDING)], unique=True, name="uq_ticket_submission")
    tickets.create_index([("status", ASCENDING), ("opened_at", DESCENDING)], name="ticket_status_recent")
    tickets.create_index([("store_id", ASCENDING), ("opened_at", DESCENDING)], name="ticket_store_recent")

    events = ticket_events_collection()
    events.create_index([("id", ASCENDING)], unique=True, name="uq_ticket_event_id")
    events.create_index([("ticket_id", ASCENDING), ("created_at", ASCENDING)], name="ticket_event_history")

    rewards = rewards_collection()
    rewards.create_index([("id", ASCENDING)], unique=True, name="uq_reward_id")
    rewards.create_index([("submission_id", ASCENDING)], unique=True, name="uq_reward_submission")
    rewards.create_index([("status", ASCENDING), ("issued_at", DESCENDING)], name="reward_status_recent")

    customer_emails_collection().create_index(
        [("submission_id", ASCENDING), ("created_at", ASCENDING)],
        name="customer_email_history",
    )
    reward_eligibility_collection().create_index(
        [("submission_id", ASCENDING)], unique=True, name="uq_reward_eligibility_submission",
    )


def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
