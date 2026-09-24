from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
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

    def get(self, ticket_id: str) -> dict | None:
        with closing(sqlite3.connect(self.path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            return self.serialize(row) if row else None