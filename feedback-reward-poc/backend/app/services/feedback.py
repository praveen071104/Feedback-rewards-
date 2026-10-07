"""Orchestrates: save feedback -> triage -> reward -> ticket."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.db import mongo
from app.llm.base import BaseAI
from app.llm.triage import enforce_rules, triage
from app.models.schemas import FeedbackSubmission, FeedbackSubmissionResult, RewardOut
from app.services.customer_emails import (
    GENERIC_ACK_CONTENT,
    GENERIC_ACK_SUBJECT,
    format_email,
    record_simulated_email,
)
from app.services import tickets
from app.services.rewards import pounds_for

GENERIC_ACK_BODY = format_email(GENERIC_ACK_SUBJECT, GENERIC_ACK_CONTENT)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _save_feedback_doc(payload: FeedbackSubmission) -> dict:
    doc = {
        "submission_id": str(payload.submission_id),
        "name": payload.name,
        "email": payload.email,
        "phone": payload.phone,
        "store_id": payload.store_id,
        "stars": payload.stars,
        "text": payload.feedback,
        "sparks_member": payload.sparks_member,
        "sparks_id": payload.sparks_id,
        "created_at": _utcnow(),
    }
    mongo.feedback_collection().insert_one(doc)
    return doc


def _record_customer_email(payload: FeedbackSubmission, kind: str, subject: str, body: str) -> dict:
    return record_simulated_email(
        str(payload.submission_id), payload.email, kind, subject, body,
    )


def _save_analysis_doc(payload: FeedbackSubmission, result: dict[str, Any], model: str, prompt_version: str) -> None:
    mongo.analysis_collection().insert_one({
        "submission_id": str(payload.submission_id),
        "model": model,
        "prompt_version": prompt_version,
        "created_at": _utcnow(),
        **result,
    })


def _reward_suggestion(tier: str) -> RewardOut:
    amount_gbp = float(pounds_for(tier))
    if tier == "none" or amount_gbp == 0:
        return RewardOut(tier="none", amount_gbp=0, status="awaiting_eligibility_review")
    return RewardOut(tier=tier, amount_gbp=amount_gbp, status="awaiting_eligibility_review")


def _enforce_rules(result: dict[str, Any]) -> tuple[bool, list[str]]:
    return enforce_rules(result)


def submit_feedback(ai: BaseAI, payload: FeedbackSubmission) -> FeedbackSubmissionResult:
    _save_feedback_doc(payload)
    acknowledgement = _record_customer_email(
        payload, "acknowledgement", GENERIC_ACK_SUBJECT, GENERIC_ACK_CONTENT,
    )

    result = triage(
        ai, feedback=payload.feedback, stars=payload.stars, store_id=payload.store_id,
        sparks_member=payload.sparks_member,
    )
    if result is None:
        result = {
            "category": "minor_complaint" if payload.stars <= 2 else "minor_compliment",
            "genuine": False,
            "has_sufficient_detail": False,
            "reward_tier": "none",
            "needs_ticket": False,
            "priority": "low",
            "staff_summary": payload.feedback[:140],
            "aspects": [],
        }

    result["sparks_member"] = payload.sparks_member
    detailed, missing = _enforce_rules(result)

    if result.get("trace") is not None:
        result["trace"].setdefault("reward", {})["amount_gbp"] = float(pounds_for(result["reward_tier"]))
    result["customer_reply"] = acknowledgement["body"]

    reward = _reward_suggestion(result["reward_tier"])
    result["reward_followup"] = None

    ticket_id = None
    if result["needs_ticket"]:
        ticket = tickets.open_ticket(
            submission_id=payload.submission_id,
            category=result["category"],
            priority=result["priority"],
            store_id=payload.store_id,
            customer_name=payload.name,
            customer_email=payload.email,
            summary=result["staff_summary"],
            assignee="Customer Care" if result["category"] == "serious_complaint" else None,
        )
        ticket_id = ticket["id"]

    _save_analysis_doc(payload, result, model=ai.model, prompt_version=ai.prompt_version)

    return FeedbackSubmissionResult(
        submission_id=payload.submission_id,
        category=result["category"],
        customer_reply=result["customer_reply"],
        reward_followup=None,
        reward=reward,
        ticket_id=ticket_id,
        needs_more_detail=(not detailed) and result["category"] in ("minor_complaint", "serious_complaint", "major_compliment"),
    )
