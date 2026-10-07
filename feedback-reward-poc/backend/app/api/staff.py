"""Staff endpoints: ticket queue + rewards + insights."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import current_staff
from app.db import mongo
from app.llm.replies import compose
from app.llm.triage import enforce_rules, triage
from app.models.schemas import (
    InsightsOut,
    RewardEligibilityDecision,
    RewardEligibilityOut,
    RewardQueueItem,
    TicketDetailOut,
    TicketEventOut,
    TicketOut,
    TicketUpdate,
)
from app.services import tickets as ticket_service
from app.services import rewards_service
from app.services.rewards import pounds_for
from app.services import dataflow as dataflow_service
from app.services.feedback_detail import feedback_detail
from app.services.insights import build_insights

router = APIRouter(prefix="/api/staff", tags=["staff"])


class AnalyseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feedback: str = Field(min_length=1, max_length=2000)
    stars: int = Field(ge=1, le=5)
    sparks_member: bool = False


@router.post("/analyse")
def analyse(body: AnalyseRequest, request: Request, _: dict = Depends(current_staff)) -> dict:
    """Run the analyser on any text without saving anything."""
    ai = request.app.state.ai
    payload = {"feedback": body.feedback.strip(), "stars": body.stars, "sparks_member": body.sparks_member}
    responder = getattr(ai, "responder", None)
    result = responder("triage", payload, {}) if responder else triage(
        ai, body.feedback, body.stars, "unspecified", sparks_member=body.sparks_member,
    )
    if result is None:
        raise HTTPException(status_code=503, detail="Analyser unavailable.")
    result["sparks_member"] = body.sparks_member
    detailed, missing = enforce_rules(result)
    if result.get("trace") is not None:
        result["trace"].setdefault("reward", {})["amount_gbp"] = float(pounds_for(result["reward_tier"]))
    result["customer_reply"] = compose(
        category=result["category"], text=body.feedback, aspects=result.get("aspects") or [],
        detailed=detailed, missing=missing, needs_ticket=result["needs_ticket"],
        reward_tier=result["reward_tier"],
        reward_amount_gbp=float(pounds_for(result["reward_tier"])),
    )
    return result


def _ticket_to_out(ticket) -> TicketOut:
    return TicketOut(
        id=ticket["id"], submission_id=ticket["submission_id"], category=ticket["category"],
        priority=ticket["priority"], status=ticket["status"], assignee=ticket.get("assignee"),
        store_id=ticket.get("store_id"), customer_name=ticket.get("customer_name"),
        customer_email=ticket.get("customer_email"), summary=ticket["summary"],
        opened_at=ticket["opened_at"], closed_at=ticket.get("closed_at"),
        resolution_notes=ticket.get("resolution_notes"),
    )


@router.get("/tickets", response_model=list[TicketOut])
def list_tickets(
    status_filter: str | None = None,
    store_id: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    _: dict = Depends(current_staff),
) -> list[TicketOut]:
    tickets = ticket_service.list_tickets(
        status=status_filter or None,
        store_id=store_id or None,
        priority=priority or None,
        category=category or None,
    )
    return [_ticket_to_out(t) for t in tickets]


@router.get("/tickets/{ticket_id}", response_model=TicketDetailOut)
def get_ticket(
    ticket_id: int,
    _: dict = Depends(current_staff),
) -> TicketDetailOut:
    ticket = ticket_service.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    feedback_doc = mongo.feedback_collection().find_one({"submission_id": ticket["submission_id"]})
    analysis_doc = mongo.analysis_collection().find_one({"submission_id": ticket["submission_id"]})

    return TicketDetailOut(
        **_ticket_to_out(ticket).model_dump(),
        events=[TicketEventOut(id=e["id"], event_type=e["event_type"], actor=e["actor"],
                       note=e.get("note"), created_at=e["created_at"]) for e in ticket["events"]],
        customer_reply=(analysis_doc or {}).get("customer_reply"),
        reward_followup=(analysis_doc or {}).get("reward_followup"),
        feedback=(feedback_doc or {}).get("text"),
        stars=(feedback_doc or {}).get("stars"),
        sparks_member=(feedback_doc or {}).get("sparks_member"),
        sparks_id=(feedback_doc or {}).get("sparks_id"),
        aspects=(analysis_doc or {}).get("aspects"),
        overall_sentiment=(analysis_doc or {}).get("overall_sentiment"),
        overall_score=(analysis_doc or {}).get("overall_score"),
    )


@router.patch("/tickets/{ticket_id}", response_model=TicketOut)
def patch_ticket(
    ticket_id: int,
    update: TicketUpdate,
    user: dict = Depends(current_staff),
) -> TicketOut:
    ticket = ticket_service.update_ticket(
        ticket_id, actor=user["username"],
        status=update.status, assignee=update.assignee,
        resolution_notes=update.resolution_notes, note=update.note,
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return _ticket_to_out(ticket)


@router.get("/insights", response_model=InsightsOut)
def insights(
    store_id: str | None = None,
    limit_recent: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(current_staff),
) -> InsightsOut:
    data = build_insights(limit_recent=limit_recent, offset=offset, store_id=store_id or None)
    for row in data["recent"]:
        ts = row.get("created_at")
        if isinstance(ts, datetime) and ts.tzinfo is None:
            row["created_at"] = ts.replace(tzinfo=timezone.utc)
    return InsightsOut(**data)


@router.get("/dataflow")
def dataflow(_: dict = Depends(current_staff)) -> dict:
    return dataflow_service.overview()


@router.get("/dataflow/{submission_id}")
def dataflow_follow(submission_id: str, _: dict = Depends(current_staff)) -> dict:
    result = dataflow_service.follow(submission_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Feedback not found.")
    return result


@router.get("/feedback/{submission_id}")
def get_feedback_detail(
    submission_id: str,
    _: dict = Depends(current_staff),
) -> dict:
    detail = feedback_detail(submission_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Feedback not found.")
    return detail


@router.patch("/feedback/{submission_id}/reward-eligibility", response_model=RewardEligibilityOut)
def decide_reward_eligibility(
    submission_id: str,
    decision: RewardEligibilityDecision,
    user: dict = Depends(current_staff),
) -> RewardEligibilityOut:
    try:
        result = rewards_service.decide_eligibility(
            submission_id, actor=user["username"], tier=decision.tier, note=decision.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail="Feedback not found.")
    return RewardEligibilityOut(**result)


@router.get("/rewards", response_model=list[RewardQueueItem])
def list_rewards(_: dict = Depends(current_staff)) -> list[RewardQueueItem]:
    rows = rewards_service.list_rewards()
    return [RewardQueueItem(**r) for r in rows]
