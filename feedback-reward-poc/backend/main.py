import logging
import os
from pathlib import Path
import sqlite3
from contextlib import asynccontextmanager
from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from predict import FeedbackPredictor
from tickets import TicketStore


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.tickets = TicketStore(Path(os.environ.get(
        "FEEDBACK_TICKETS_DB", str(Path(__file__).resolve().parent / "tickets.sqlite3"),
    )))
    try:
        application.state.predictor = FeedbackPredictor()
    except (FileNotFoundError, ValueError, EOFError, ImportError, OSError):
        logging.exception("Models unavailable. Train both models with this environment and restart the API.")
        application.state.predictor = None
    yield


app = FastAPI(title="Customer Feedback Reward Recommendation System", version="0.1.0", lifespan=lifespan)


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feedback: str = Field(min_length=1, max_length=5000)
    submissionId: UUID = Field(default_factory=uuid4)
    loyalCustomer: bool = Field(default=False, strict=True)

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, value: str) -> str:
        value = value.strip()
        if not value or not any(character.isalpha() for character in value):
            raise ValueError("Feedback must contain at least one letter")
        return value


Category = Literal["ignored", "compliment", "major_compliment", "minor_complaint", "serious_complaint", "needs_clarification"]
RewardDecision = Literal["eligible", "not_eligible", "pending"]


class TicketResponse(BaseModel):
    id: UUID
    feedback: str
    category: Literal["minor_complaint", "serious_complaint"]
    rewardDecision: RewardDecision
    priority: Literal["normal", "priority"]
    status: Literal["open"]
    createdAt: str


class PredictionResponse(BaseModel):
    sentiment: Literal["Positive", "Neutral", "Negative"]
    sentimentConfidence: float = Field(ge=0, le=1)
    genuineFeedback: Literal["Yes", "No"]
    genuineConfidence: float = Field(ge=0, le=1)
    rewardEligible: bool
    reason: str
    category: Category
    rewardDecision: RewardDecision
    customerResponse: str
    ticketRequired: bool
    incentiveTier: Literal["none", "tier_based", "high"]
    ticket: TicketResponse | None = None


@app.get("/health")
def health(request: Request):
    ready = request.app.state.predictor is not None
    return {"status": "ready" if ready else "models_missing", "modelsLoaded": ready}


@app.post("/predict", response_model=PredictionResponse)
def predict_feedback(payload: FeedbackRequest, request: Request):
    predictor = request.app.state.predictor
    if predictor is None:
        raise HTTPException(503, "Models unavailable. Train both models and restart the API.")
    result = predictor.predict(payload.feedback, payload.loyalCustomer)
    if result["ticketRequired"]:
        try:
            result["ticket"] = request.app.state.tickets.open(str(payload.submissionId), payload.feedback, result)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        except sqlite3.Error as error:
            logging.exception("Ticket storage unavailable")
            raise HTTPException(503, "Ticket storage unavailable. Please retry this submission.") from error
    return result


@app.get("/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: UUID, request: Request):
    try:
        ticket = request.app.state.tickets.get(str(ticket_id))
    except sqlite3.Error as error:
        raise HTTPException(503, "Ticket storage unavailable.") from error
    if ticket is None:
        raise HTTPException(404, "Ticket not found.")
    return ticket