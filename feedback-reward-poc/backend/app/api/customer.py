"""Public customer endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_ai
from app.llm.base import BaseAI
from app.models.schemas import FeedbackSubmission, FeedbackSubmissionResult
from app.services.feedback import submit_feedback

router = APIRouter(prefix="/api", tags=["customer"])


@router.get("/stores")
def stores() -> list[dict]:
    return [
        {"id": "marble-arch", "name": "Marble Arch"},
        {"id": "stratford-city", "name": "Stratford City"},
        {"id": "bluewater", "name": "Bluewater"},
        {"id": "unspecified", "name": "Not specified"},
    ]


@router.post("/feedback", response_model=FeedbackSubmissionResult)
def post_feedback(
    payload: FeedbackSubmission,
    ai: BaseAI = Depends(get_ai),
) -> FeedbackSubmissionResult:
    return submit_feedback(ai, payload)
