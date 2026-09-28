import logging
import os
from pathlib import Path
import sqlite3
from contextlib import asynccontextmanager
from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pymongo.errors import PyMongoError

from feedback_store import FeedbackStore, STORES
from predict import FeedbackPredictor
from tickets import TicketStore
from cases import CaseStore, router as cases_router


class PrivateQueryFilter(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            client, method, path, version, status = record.args
            record.args = (client, method, str(path).partition("?")[0], version, status)
        return True


logging.getLogger("uvicorn.access").addFilter(PrivateQueryFilter())


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.feedback = FeedbackStore()
    application.state.cases = CaseStore(application.state.feedback.collection.database)
    application.state.tickets = TicketStore(Path(os.environ.get(
        "FEEDBACK_TICKETS_DB", str(Path(__file__).resolve().parent / "tickets.sqlite3"),
    )))
    try:
        application.state.predictor = FeedbackPredictor()
    except (FileNotFoundError, ValueError, EOFError, ImportError, OSError):
        logging.exception("Models unavailable. Train both models with this environment and restart the API.")
        application.state.predictor = None
    try:
        yield
    finally:
        application.state.feedback.close()


app = FastAPI(title="Customer Feedback Reward Recommendation System", version="0.1.0", lifespan=lifespan)
app.include_router(cases_router)


@app.exception_handler(PyMongoError)
async def mongo_unavailable(request: Request, error: PyMongoError):
    return JSONResponse(status_code=503, content={"detail": "Feedback storage unavailable. Please retry; saving was not confirmed."})


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feedback: str = Field(min_length=1, max_length=5000)
    submissionId: UUID = Field(default_factory=uuid4)
    loyalCustomer: bool = Field(default=False, strict=True)
    storeId: Literal["marble-arch", "stratford-city", "bluewater", "unspecified"] = "unspecified"

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, value: str) -> str:
        value = value.strip()
        if not value or not any(character.isalpha() for character in value):
            raise ValueError("Feedback must contain at least one letter")
        return value


Category = Literal["ignored", "compliment", "major_compliment", "minor_complaint", "serious_complaint", "needs_clarification", "suggestion"]
RewardDecision = Literal["eligible", "not_eligible", "pending"]


class TicketResponse(BaseModel):
    id: UUID
    feedback: str
    category: Literal["minor_complaint", "serious_complaint"]
    rewardDecision: RewardDecision
    priority: Literal["normal", "priority"]
    status: Literal["open"]
    createdAt: str


class ClarificationRequest(FeedbackRequest):
    feedbackId: UUID
    originalFeedback: str = Field(min_length=1, max_length=5000)
    ticketId: UUID | None = None

    @field_validator("originalFeedback")
    @classmethod
    def validate_original(cls, value: str) -> str:
        return cls.validate_feedback(value)


class PredictionResponse(BaseModel):
    feedbackId: UUID
    feedback: str
    storeId: str
    store: dict[str, str]
    loyalCustomer: bool
    createdAt: int
    updatedAt: int
    revision: int
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
    clarificationQuestions: list[str]
    ticket: TicketResponse | None = None


class FeedbackHistory(BaseModel):
    items: list[PredictionResponse]
    nextCursor: UUID | None


class WorkflowFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["open", "in_progress", "resolved"] = "open"
    assignee: str = Field(default="", max_length=120)
    customerEmail: str = Field(default="", max_length=254, pattern=r"^(?:[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+)?$")
    contactConsent: bool = Field(default=False, strict=True)
    contactStatus: Literal["not_contacted", "contact_recorded"] = "not_contacted"
    actionTaken: str = Field(default="", max_length=2000)
    customerUpdate: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_workflow(self):
        if self.status != "open" and not self.assignee:
            raise ValueError("Assign a colleague before starting or resolving work.")
        if self.status == "resolved" and (not self.actionTaken or not self.customerUpdate):
            raise ValueError("Record the completed action and customer update before resolving.")
        if self.customerEmail and not self.contactConsent:
            raise ValueError("Customer permission is required to store contact details.")
        if self.contactStatus == "contact_recorded" and not (
            self.assignee and self.customerEmail and self.contactConsent and self.customerUpdate
        ):
            raise ValueError("Record an owner, permitted customer email and update before confirming contact.")
        return self


class WorkflowRequest(WorkflowFields):
    operationId: UUID
    expectedVersion: int = Field(ge=0)


@app.get("/tickets/{ticket_id}/workflow")
def get_workflow(ticket_id: UUID, request: Request):
    try:
        return request.app.state.tickets.workflow(str(ticket_id))
    except KeyError as error:
        raise HTTPException(404, "Ticket not found.") from error
    except sqlite3.Error as error:
        raise HTTPException(503, "Ticket storage unavailable.") from error


@app.put("/tickets/{ticket_id}/workflow")
def update_workflow(ticket_id: UUID, payload: WorkflowRequest, request: Request):
    try:
        return request.app.state.tickets.update_workflow(
            str(ticket_id), str(payload.operationId), payload.expectedVersion,
            payload.model_dump(exclude={"operationId", "expectedVersion"}),
        )
    except KeyError as error:
        raise HTTPException(404, "Ticket not found.") from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    except sqlite3.Error as error:
        raise HTTPException(503, "Ticket storage unavailable. Retry the same update.") from error


@app.get("/stores")
def list_stores():
    return [{"id": identity, **store} for identity, store in STORES.items()]


@app.get("/feedback", response_model=FeedbackHistory)
def feedback_history(request: Request, before: UUID | None = None, limit: int = Query(default=100, ge=1, le=200)):
    try:
        return request.app.state.feedback.list(str(before) if before else None, limit)
    except KeyError as error:
        raise HTTPException(404, "History cursor not found.") from error


@app.get("/health")
def health(request: Request):
    ready = request.app.state.predictor is not None
    try:
        request.app.state.feedback.ping()
        storage_ready = True
    except PyMongoError:
        storage_ready = False
    return {"status": "models_missing" if not ready else "ready" if storage_ready else "storage_unavailable",
            "modelsLoaded": ready, "storageReady": storage_ready}


@app.post("/predict", response_model=PredictionResponse)
def predict_feedback(payload: FeedbackRequest, request: Request):
    predictor = request.app.state.predictor
    if predictor is None:
        raise HTTPException(503, "Models unavailable. Train both models and restart the API.")
    saved_request = {"feedback": payload.feedback, "storeId": payload.storeId, "loyalCustomer": payload.loyalCustomer}
    try:
        saved = request.app.state.feedback.initial(str(payload.submissionId), saved_request)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    if saved is not None:
        return saved
    result = predictor.predict(payload.feedback, payload.loyalCustomer)
    if result["ticketRequired"]:
        try:
            result["ticket"] = request.app.state.tickets.open(str(payload.submissionId), payload.feedback, result)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        except sqlite3.Error as error:
            logging.exception("Ticket storage unavailable")
            raise HTTPException(503, "Ticket storage unavailable. Please retry this submission.") from error
    try:
        return request.app.state.feedback.save(str(payload.submissionId), saved_request, result)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.post("/clarify", response_model=PredictionResponse)
def clarify_feedback(payload: ClarificationRequest, request: Request):
    predictor = request.app.state.predictor
    if predictor is None:
        raise HTTPException(503, "Models unavailable. Train both models and restart the API.")
    combined = payload.originalFeedback + "\n\n" + payload.feedback
    if len(combined) > 5000:
        raise HTTPException(422, "Feedback and clarification together must not exceed 5,000 characters.")
    saved_request = {
        "originalFeedback": payload.originalFeedback, "feedback": payload.feedback,
        "storeId": payload.storeId, "loyalCustomer": payload.loyalCustomer,
        "ticketId": str(payload.ticketId) if payload.ticketId else None,
    }
    try:
        saved = request.app.state.feedback.clarification(str(payload.feedbackId), str(payload.submissionId), saved_request)
    except KeyError as error:
        raise HTTPException(404, "Saved feedback not found.") from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    if saved is not None:
        return saved
    original = predictor.predict(payload.originalFeedback, payload.loyalCustomer)
    if not original["clarificationQuestions"]:
        raise HTTPException(409, "This feedback does not require clarification. Submit new feedback instead.")
    if original["ticketRequired"] and payload.ticketId is None:
        raise HTTPException(422, "The existing complaint ticket reference is required.")
    result = predictor.predict(combined, payload.loyalCustomer)
    try:
        if payload.ticketId is not None:
            result = request.app.state.tickets.reassess(
                str(payload.ticketId), str(payload.submissionId), payload.originalFeedback,
                combined, payload.loyalCustomer, result,
            )
        elif result["ticketRequired"]:
            result["ticket"] = request.app.state.tickets.open(str(payload.submissionId), combined, result)
        return request.app.state.feedback.update(str(payload.feedbackId), str(payload.submissionId), saved_request, result)
    except KeyError as error:
        raise HTTPException(404, "Ticket not found.") from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    except sqlite3.Error as error:
        logging.exception("Ticket storage unavailable during reassessment")
        raise HTTPException(503, "Ticket storage unavailable. Please retry this clarification.") from error


@app.get("/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: UUID, request: Request):
    try:
        ticket = request.app.state.tickets.get(str(ticket_id))
    except sqlite3.Error as error:
        raise HTTPException(503, "Ticket storage unavailable.") from error
    if ticket is None:
        raise HTTPException(404, "Ticket not found.")
    return ticket