from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from uuid import uuid4


class TicketStore:
    def __init__(self, path: Path):
        self.path = path
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS tickets ("
                "id TEXT PRIMARY KEY, submission_id TEXT UNIQUE NOT NULL, "
                "feedback TEXT NOT NULL, category TEXT NOT NULL, "
                "reward_decision TEXT NOT NULL, priority TEXT NOT NULL, "
                "status TEXT NOT NULL, created_at TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS ticket_reassessments ("
                "submission_id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL, "
                "previous_feedback TEXT NOT NULL, feedback TEXT NOT NULL, "
                "loyal_customer INTEGER NOT NULL, response TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS ticket_workflows (ticket_id TEXT PRIMARY KEY, document TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS ticket_workflow_operations ("
                "operation_id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL, request TEXT NOT NULL, response TEXT NOT NULL)"
            )

    @staticmethod
    def empty_workflow(ticket_id):
        return {"ticketId": ticket_id, "version": 0, "status": "open", "assignee": "",
                "customerEmail": "", "contactConsent": False, "contactStatus": "not_contacted",
                "actionTaken": "", "customerUpdate": "", "updatedAt": None, "history": []}

    def workflow(self, ticket_id):
        with closing(sqlite3.connect(self.path)) as connection:
            if connection.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
                raise KeyError(ticket_id)
            row = connection.execute("SELECT document FROM ticket_workflows WHERE ticket_id = ?", (ticket_id,)).fetchone()
            return json.loads(row[0]) if row else self.empty_workflow(ticket_id)

    def update_workflow(self, ticket_id, operation_id, expected_version, fields):
        payload = json.dumps({"version": expected_version, **fields}, sort_keys=True)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
                raise KeyError(ticket_id)
            previous = connection.execute(
                "SELECT ticket_id, request, response FROM ticket_workflow_operations WHERE operation_id = ?", (operation_id,),
            ).fetchone()
            if previous:
                if previous[0] != ticket_id or previous[1] != payload:
                    raise ValueError("This update ID was used for different details.")
                return json.loads(previous[2])
            row = connection.execute("SELECT document FROM ticket_workflows WHERE ticket_id = ?", (ticket_id,)).fetchone()
            current = json.loads(row[0]) if row else self.empty_workflow(ticket_id)
            if current["version"] != expected_version:
                raise ValueError("This ticket has newer action details. Reload before saving.")
            if current["status"] == "resolved" and fields["status"] != "resolved":
                raise ValueError("A resolved ticket cannot be reopened through this form.")
            now = datetime.now(timezone.utc).isoformat()
            updated = {**current, **fields, "version": current["version"] + 1, "updatedAt": now,
                       "history": [*current["history"], {**fields, "recordedAt": now}]}
            response = json.dumps(updated)
            connection.execute(
                "INSERT INTO ticket_workflows VALUES (?, ?) ON CONFLICT(ticket_id) DO UPDATE SET document = excluded.document",
                (ticket_id, response),
            )
            connection.execute("INSERT INTO ticket_workflow_operations VALUES (?, ?, ?, ?)",
                               (operation_id, ticket_id, payload, response))
            return updated

    @staticmethod
    def serialize(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "feedback": row["feedback"],
            "category": row["category"],
            "rewardDecision": row["reward_decision"],
            "priority": row["priority"],
            "status": row["status"],
            "createdAt": row["created_at"],
        }

    def open(self, submission_id: str, feedback: str, result: dict) -> dict:
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.row_factory = sqlite3.Row
            connection.execute(
                "INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(submission_id) DO NOTHING",
                (str(uuid4()), submission_id, feedback, result["category"],
                 result["rewardDecision"], "priority" if result["category"] == "serious_complaint" else "normal",
                 "open", datetime.now(timezone.utc).isoformat()),
            )
            row = connection.execute("SELECT * FROM tickets WHERE submission_id = ?", (submission_id,)).fetchone()
            if row["feedback"] != feedback:
                raise ValueError("This submission ID was already used for different feedback.")
            return self.serialize(row)

    def reassess(self, ticket_id: str, submission_id: str, previous_feedback: str,
                 feedback: str, loyal_customer: bool, result: dict) -> dict:
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute(
                "SELECT * FROM ticket_reassessments WHERE submission_id = ?", (submission_id,),
            ).fetchone()
            if previous:
                if (previous["ticket_id"], previous["previous_feedback"], previous["feedback"], previous["loyal_customer"]) != (
                    ticket_id, previous_feedback, feedback, loyal_customer,
                ):
                    raise ValueError("This clarification ID was already used for different details.")
                return json.loads(previous["response"])
            row = connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            if row is None:
                raise KeyError(ticket_id)
            if row["feedback"] != previous_feedback:
                raise ValueError("This ticket has newer feedback. Reload its latest details before replying.")
            if not result["ticketRequired"]:
                raise ValueError("This clarification cannot remove an existing complaint ticket.")
            connection.execute(
                "UPDATE tickets SET feedback = ?, category = ?, reward_decision = ?, priority = ? WHERE id = ?",
                (feedback, result["category"], result["rewardDecision"],
                 "priority" if result["category"] == "serious_complaint" else "normal", ticket_id),
            )
            result = {**result, "ticket": self.serialize(connection.execute(
                "SELECT * FROM tickets WHERE id = ?", (ticket_id,),
            ).fetchone())}
            connection.execute(
                "INSERT INTO ticket_reassessments VALUES (?, ?, ?, ?, ?, ?)",
                (submission_id, ticket_id, previous_feedback, feedback, loyal_customer, json.dumps(result)),
            )
            return result

    def get(self, ticket_id: str) -> dict | None:
        with closing(sqlite3.connect(self.path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            return self.serialize(row) if row else None