
"""Ticket CRUD + event trail."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from app.db import mongo


def _append_event(ticket_id: int, event_type: str, actor: str, note: str | None) -> None:
    mongo.ticket_events_collection().insert_one({
        "id": mongo.next_id("ticket_event"),
        "ticket_id": ticket_id,
        "event_type": event_type,
        "actor": actor,
        "note": note,
        "created_at": datetime.now(timezone.utc),
    })


def open_ticket(*, submission_id: UUID, category: str, priority: str,
                store_id: str | None, customer_name: str | None, customer_email: str | None,
                summary: str, assignee: str | None = None) -> dict:
    ticket = {
        "id": mongo.next_id("ticket"),
        "submission_id": str(submission_id),
        "category": category,
        "priority": priority,
        "status": "open",
        "assignee": assignee,
        "store_id": store_id,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "summary": summary,
        "opened_at": datetime.now(timezone.utc),
        "closed_at": None,
        "resolution_notes": None,
    }
    mongo.tickets_collection().insert_one(ticket)
    _append_event(ticket["id"], "opened", "system", f"Auto-opened from feedback ({category}).")
    if assignee:
        _append_event(ticket["id"], "assigned", "system", f"Assigned to {assignee}")
    return ticket


def list_tickets(
    *,
    status: str | None = None,
    store_id: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    assignee: str | None = None,
    limit: int = 100,
) -> list[dict]:
    query = {key: value for key, value in {
        "status": status, "store_id": store_id, "priority": priority,
        "category": category, "assignee": assignee,
    }.items() if value}
    return list(mongo.tickets_collection().find(query, {"_id": 0}).sort("opened_at", -1).limit(limit))


def get_ticket(ticket_id: int) -> dict | None:
    ticket = mongo.tickets_collection().find_one({"id": ticket_id}, {"_id": 0})
    if ticket is not None:
        ticket["events"] = list(mongo.ticket_events_collection().find(
            {"ticket_id": ticket_id}, {"_id": 0},
        ).sort("created_at", 1))
    return ticket


def update_ticket(ticket_id: int, actor: str, *, status: str | None = None,
                  assignee: str | None = None, resolution_notes: str | None = None,
                  note: str | None = None) -> dict | None:
    collection = mongo.tickets_collection()
    ticket = collection.find_one({"id": ticket_id}, {"_id": 0})
    if ticket is None:
        return None

    changes: dict = {}
    if assignee is not None and assignee != (ticket.get("assignee") or ""):
        changes["assignee"] = assignee or None
        _append_event(ticket_id, "assigned", actor, f"Assigned to {assignee}" if assignee else "Unassigned")
    if status is not None and status != ticket["status"]:
        changes["status"] = status
        if status == "resolved":
            changes["closed_at"] = datetime.now(timezone.utc)
        _append_event(ticket_id, "status_changed", actor, f"Status: {status}")
    if resolution_notes is not None:
        changes["resolution_notes"] = resolution_notes or None
    if note:
        _append_event(ticket_id, "note", actor, note)
    if changes:
        collection.update_one({"id": ticket_id}, {"$set": changes})
    return get_ticket(ticket_id)


def counts_by_status() -> dict[str, int]:
    return {
        row["_id"]: int(row["count"])
        for row in mongo.tickets_collection().aggregate([
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ])
    }
