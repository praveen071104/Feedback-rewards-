from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import re
from typing import Literal
from uuid import UUID, NAMESPACE_URL, uuid5

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

CaseStatus = Literal["Opened", "In Progress", "Resolved"]
Decision = Literal["Reward Eligible", "Not Eligible", "Awaiting Colleague Review"]
Template = Literal["reward_eligible", "not_eligible", "general"]
logger = logging.getLogger(__name__)
TEMPLATES = {
    "reward_eligible": "Thank you for sharing your feedback. Your submission has been reviewed and is eligible for a reward. A confirmation has been recorded{account}.",
    "not_eligible": "Thank you for sharing your feedback. Your submission has been reviewed and does not currently meet the reward eligibility criteria.",
    "general": "Thank you for your feedback. Your submission has been reviewed and the case has been updated.",
}


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CustomerSubmission(InputModel):
    submission_id: UUID
    name: str = Field(min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=254)
    phone_number: str | None = Field(default=None, max_length=30)
    is_sparks_customer: bool = Field(strict=True)
    sparks_id: str | None = Field(default=None, max_length=64)
    store_id: Literal["marble-arch", "stratford-city", "bluewater", "unspecified"] = "unspecified"
    feedback: str = Field(min_length=1, max_length=5000)
    rating: int = Field(ge=1, le=5, strict=True)

    @field_validator("email", "phone_number", "sparks_id", mode="before")
    @classmethod
    def empty_to_null(cls, value):
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("name", "feedback", "sparks_id")
    @classmethod
    def safe_text(cls, value):
        if value is not None and any(ord(character) < 32 and character not in "\n\t" for character in value):
            raise ValueError("Control characters are not allowed.")
        return value

    @field_validator("feedback")
    @classmethod
    def feedback_letters(cls, value):
        if not any(character.isalpha() for character in value):
            raise ValueError("Feedback must contain at least one letter.")
        return value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        if value is not None and (not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+", value)
                                  or ".." in value or value.startswith(".") or ".@" in value):
            raise ValueError("Enter a valid email address.")
        return value

    @field_validator("phone_number")
    @classmethod
    def valid_phone(cls, value):
        if value is not None:
            if not re.fullmatch(r"\+?[0-9 ()-]+", value) or not 7 <= len(re.sub(r"\D", "", value)) <= 15:
                raise ValueError("Enter a phone number with 7 to 15 digits.")
            return ("+" if value.startswith("+") else "") + re.sub(r"\D", "", value)
        return value

    @model_validator(mode="after")
    def required_contact(self):
        if not self.email and not self.phone_number:
            raise ValueError("Provide an email address or phone number.")
        if self.is_sparks_customer and not self.sparks_id:
            raise ValueError("Sparks ID is required for a Sparks customer.")
        if not self.is_sparks_customer:
            self.sparks_id = None
        return self


class CaseUpdate(InputModel):
    operation_id: UUID
    expected_version: int = Field(ge=0)
    case_status: CaseStatus
    final_decision: Decision
    decision_reason: str = Field(min_length=1, max_length=1000)
    confirmed_by: str = Field(min_length=1, max_length=120)
    colleague_note: str = Field(default="", max_length=2000)
    store_id: Literal["marble-arch", "stratford-city", "bluewater", "unspecified"]


class CommunicationRequest(InputModel):
    operation_id: UUID
    expected_version: int = Field(ge=0)
    template: Template


class CustomerProfile(BaseModel):
    customer_id: str
    name: str
    email: str | None
    phone_number: str | None
    is_sparks_customer: bool
    sparks_id: str | None
    created_at: datetime
    updated_at: datetime


class Sentiment(BaseModel):
    label: Literal["Positive", "Neutral", "Negative"]
    confidence: float
    model_name: str
    model_version: str
    confidence_kind: str
    rating_sentiment: Literal["Positive", "Neutral", "Negative"] | None = None
    rating_conflict: bool = False


class Assessment(BaseModel):
    model_recommendation: Decision
    model_confidence: float
    model_label: Literal["Yes", "No"]
    model_name: str
    model_version: str
    threshold: float
    reason_code: str
    model_reason: str
    category: str
    incentive_tier: str
    final_decision: Decision | None = None
    decision_reason: str | None = None
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None


class Notification(BaseModel):
    is_new: bool
    is_read: bool
    created_at: datetime
    read_at: datetime | None = None


class Communication(BaseModel):
    channel: str | None = None
    template: Template | None = None
    message: str | None = None
    status: str = "Not Sent"
    sent_at: datetime | None = None
    is_simulated: bool = True


class Activity(BaseModel):
    action: str
    timestamp: datetime
    note: str | None = None
    colleague: str | None = None
    template: Template | None = None
    channel: str | None = None


class FeedbackCase(BaseModel):
    case_id: str
    customer_id: str
    store_id: str
    feedback: str
    rating: int
    sentiment: Sentiment
    reward_assessment: Assessment
    case_status: CaseStatus
    notification: Notification
    customer_communication: Communication
    activity_history: list[Activity]
    created_at: datetime
    updated_at: datetime
    version: int


class CaseDetail(FeedbackCase):
    customer: CustomerProfile
    communication_templates: dict[str, str]


class CasePage(BaseModel):
    items: list[FeedbackCase]
    total: int
    page: int
    page_size: int


class SubmissionResult(BaseModel):
    case_id: str
    status: Literal["submitted"] = "submitted"


class NotificationItem(BaseModel):
    case_id: str
    store_id: str
    created_at: datetime
    is_read: bool


class Notifications(BaseModel):
    unread_count: int
    items: list[NotificationItem]
    revision: int


class Insights(BaseModel):
    total: int
    statuses: dict[str, int]
    decisions: dict[str, int]
    average_rating: float | None
    sentiments: dict[str, int]
    unread_count: int


class CaseStore:
    def __init__(self, database):
        self.cases = database["feedback_cases"]
        self.profiles = database["customer_profiles"]
        self.events = database["feedback_case_events"]
        self._indexed = False

    def ensure_indexes(self):
        if self._indexed:
            return
        self.profiles.create_index("customer_id", unique=True)
        self.cases.create_index("case_id", unique=True)
        for field in ("customer_id", "store_id", "case_status", "created_at", "notification.is_read"):
            self.cases.create_index(field)
        self.cases.create_index([("created_at", -1), ("case_id", -1)])
        self._indexed = True

    @staticmethod
    def public(document):
        return {key: value for key, value in document.items() if key not in {"_id", "request_hash", "operations"}}

    @staticmethod
    def fingerprint(payload):
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def changed(self):
        self.events.update_one({"_id": "revision"}, {"$inc": {"value": 1}}, upsert=True)

    def revision(self):
        return (self.events.find_one({"_id": "revision"}) or {}).get("value", 0)

    def raw(self, case_id):
        document = self.cases.find_one({"case_id": case_id})
        if document is None:
            raise HTTPException(404, "Feedback case not found.")
        return document

    def detail(self, case_id):
        document = self.public(self.raw(case_id))
        profile = self.profiles.find_one({"customer_id": document["customer_id"]})
        if profile is None:
            raise HTTPException(503, "Customer profile unavailable. Please retry.")
        return {**document, "customer": self.public(profile), "communication_templates": {
            **TEMPLATES, "reward_eligible": TEMPLATES["reward_eligible"].format(
                account=" for your Sparks account" if profile["is_sparks_customer"] else " for your submission"),
        }}

    def submit(self, payload, predictor):
        self.ensure_indexes()
        request = payload.model_dump(mode="json")
        identity = str(payload.submission_id)
        fingerprint = self.fingerprint(request)
        existing = self.cases.find_one({"case_id": identity})
        if existing:
            if existing["request_hash"] != fingerprint:
                raise HTTPException(409, "Submission reference already used. Start a new submission for changed details.")
            self.changed()
            return {"case_id": identity, "status": "submitted"}
        customer_id = str(uuid5(NAMESPACE_URL, "feedback-customer:" + identity))
        now = datetime.now(timezone.utc)
        profile = {key: request[key] for key in ("name", "email", "phone_number", "is_sparks_customer", "sparks_id")}
        profile.update(customer_id=customer_id, created_at=now, updated_at=now, request_hash=fingerprint)
        try:
            self.profiles.insert_one({"_id": customer_id, **profile})
        except DuplicateKeyError:
            saved = self.profiles.find_one({"customer_id": customer_id})
            if saved["request_hash"] != fingerprint:
                raise HTTPException(409, "Submission reference already used for different details.") from None
        if predictor is None:
            raise HTTPException(503, "Analysis unavailable. Your submission is not complete; please retry.")
        result = predictor.predict(payload.feedback, payload.is_sparks_customer)
        rating_sentiment = "Negative" if payload.rating <= 2 else "Positive" if payload.rating >= 4 else "Neutral"
        rating_conflict = result["sentiment"] != rating_sentiment
        try:
            threshold = float(os.environ.get("REWARD_REVIEW_THRESHOLD", "0.75"))
        except ValueError:
            raise HTTPException(503, "Review threshold configuration is invalid.") from None
        if not 0 <= threshold <= 1:
            raise HTTPException(503, "Review threshold configuration is invalid.")
        conflicting = result["rewardDecision"] == "eligible" and result["genuineFeedback"] != "Yes"
        review = (result["genuineConfidence"] < threshold or result["rewardDecision"] == "pending"
              or conflicting or rating_conflict)
        recommendation = "Awaiting Colleague Review" if review else "Reward Eligible" if result["rewardDecision"] == "eligible" else "Not Eligible"
        metadata = getattr(predictor, "metadata", {})
        document = {
            "_id": identity, "case_id": identity, "customer_id": customer_id, "store_id": payload.store_id,
            "feedback": payload.feedback, "rating": payload.rating,
            "sentiment": {"label": result["sentiment"], "confidence": result["sentimentConfidence"],
                          "model_name": "Bidirectional LSTM sentiment classifier",
                          "model_version": metadata.get("sentiment", "local-existing"),
                          "confidence_kind": "LSTM softmax score; not calibrated confidence",
                          "rating_sentiment": rating_sentiment, "rating_conflict": rating_conflict},
            "reward_assessment": {
                "model_recommendation": recommendation, "model_confidence": result["genuineConfidence"],
                "model_label": result["genuineFeedback"], "model_name": "TF-IDF + Logistic Regression",
                "model_version": metadata.get("genuine", "local-existing"), "threshold": threshold,
                "reason_code": ("REVIEW_REQUIRED_RATING_SENTIMENT_MISMATCH" if rating_conflict
                                else "REVIEW_REQUIRED" if review else "EXISTING_BUSINESS_RULES"),
                "model_reason": result["reason"], "category": result["category"], "incentive_tier": result["incentiveTier"],
                "final_decision": None, "decision_reason": None, "confirmed_by": None, "confirmed_at": None,
            },
            "case_status": "Opened", "notification": {"is_new": True, "is_read": False, "created_at": now, "read_at": None},
            "customer_communication": Communication().model_dump(),
            "activity_history": [{"action": "Feedback Submitted", "timestamp": now}],
            "created_at": now, "updated_at": now, "version": 0, "request_hash": fingerprint, "operations": [],
        }
        try:
            self.cases.insert_one(document)
        except DuplicateKeyError:
            if self.raw(identity)["request_hash"] != fingerprint:
                raise HTTPException(409, "Submission reference already used for different details.") from None
        self.changed()
        logger.info("feedback_case_submitted", extra={"case_id": identity})
        return {"case_id": identity, "status": "submitted"}

    def list(self, store_id=None, status=None, search="", decision=None, page=1, page_size=20):
        query = {}
        if store_id:
            query["store_id"] = store_id
        if status:
            query["case_status"] = status
        if search:
            query["$or"] = [{field: {"$regex": re.escape(search), "$options": "i"}} for field in ("case_id", "feedback")]
        if decision:
            if decision == "Awaiting Colleague Review":
                query["reward_assessment.final_decision"] = {"$in": [None, decision]}
            else:
                query["reward_assessment.final_decision"] = decision
        documents = self.cases.find(query).sort([("created_at", -1), ("case_id", -1)]).skip((page - 1) * page_size).limit(page_size)
        return {"items": [self.public(document) for document in documents], "total": self.cases.count_documents(query), "page": page, "page_size": page_size}

    def notifications(self):
        documents = self.cases.find({}, {"case_id": 1, "store_id": 1, "created_at": 1, "notification": 1}).sort([
            ("notification.is_read", 1), ("created_at", -1), ("case_id", -1),
        ]).limit(20)
        return {"unread_count": self.cases.count_documents({"notification.is_read": False}), "revision": self.revision(),
                "items": [{"case_id": item["case_id"], "store_id": item["store_id"], "created_at": item["created_at"],
                           "is_read": item["notification"]["is_read"]} for item in documents]}

    def mark_read(self, case_id):
        self.raw(case_id)
        now = datetime.now(timezone.utc)
        self.cases.update_one({"case_id": case_id, "notification.is_read": False}, {
            "$set": {"notification.is_read": True, "notification.is_new": False, "notification.read_at": now},
            "$push": {"activity_history": {"action": "Opened by colleague", "timestamp": now}},
        })
        self.changed()
        return self.notifications()

    def mutate(self, case_id, payload, action):
        document = self.raw(case_id)
        operation_id = str(payload.operation_id)
        fingerprint = self.fingerprint({"action": action, **payload.model_dump(mode="json")})
        for operation in document["operations"]:
            if operation["id"] == operation_id:
                if operation["hash"] != fingerprint:
                    raise HTTPException(409, "Operation reference already used for a different action.")
                self.changed()
                return self.detail(case_id)
        if document["version"] != payload.expected_version:
            raise HTTPException(409, "Case changed. Reload the case before saving.")
        now = datetime.now(timezone.utc)
        fields = {"updated_at": now}
        history = {"action": action, "timestamp": now}
        if isinstance(payload, CaseUpdate):
            if document["case_status"] == "Resolved" and payload.case_status != "Resolved":
                raise HTTPException(409, "Resolved cases cannot be reopened.")
            if document["case_status"] == "In Progress" and payload.case_status == "Opened":
                raise HTTPException(409, "In-progress cases cannot move back to Opened.")
            if payload.case_status == "Resolved" and payload.final_decision == "Awaiting Colleague Review":
                raise HTTPException(409, "Confirm a reward decision before resolving the case.")
            fields.update({"case_status": payload.case_status, "store_id": payload.store_id,
                           "reward_assessment.final_decision": payload.final_decision,
                           "reward_assessment.decision_reason": payload.decision_reason,
                           "reward_assessment.confirmed_by": payload.confirmed_by,
                           "reward_assessment.confirmed_at": now if payload.final_decision != "Awaiting Colleague Review" else None})
            history.update(action=f"{payload.case_status}: {payload.final_decision}", colleague=payload.confirmed_by,
                           note=payload.decision_reason + ("\n" + payload.colleague_note if payload.colleague_note else ""))
        else:
            expected = {"reward_eligible": "Reward Eligible", "not_eligible": "Not Eligible"}.get(payload.template)
            if expected and document["reward_assessment"]["final_decision"] != expected:
                raise HTTPException(409, "Confirm the matching reward decision before sending this template.")
            detail = self.detail(case_id)
            channel = "email" if detail["customer"]["email"] else "phone"
            fields["customer_communication"] = {
                "channel": channel, "template": payload.template, "message": detail["communication_templates"][payload.template],
                "status": "Recorded (POC simulation)", "sent_at": now, "is_simulated": True,
            }
            history.update(action="Customer communication recorded (POC simulation)", template=payload.template, channel=channel)
        updated = self.cases.find_one_and_update({"case_id": case_id, "version": payload.expected_version}, {
            "$set": fields, "$inc": {"version": 1},
            "$push": {"activity_history": history, "operations": {"id": operation_id, "hash": fingerprint}},
        }, return_document=ReturnDocument.AFTER)
        if updated is None:
            return self.mutate(case_id, payload, action)
        self.changed()
        logger.info("feedback_case_updated", extra={"case_id": case_id, "action": action})
        return self.detail(case_id)

    def insights(self, store_id=None):
        query = {"store_id": store_id} if store_id else {}
        rows = list(self.cases.aggregate([{"$match": query}, {"$facet": {
            "totals": [{"$group": {"_id": None, "total": {"$sum": 1}, "average_rating": {"$avg": "$rating"},
                                    "unread_count": {"$sum": {"$cond": ["$notification.is_read", 0, 1]}}}}],
            "statuses": [{"$group": {"_id": "$case_status", "count": {"$sum": 1}}}],
            "sentiments": [{"$group": {"_id": "$sentiment.label", "count": {"$sum": 1}}}],
            "decisions": [{"$group": {"_id": {"$ifNull": ["$reward_assessment.final_decision", "Awaiting Colleague Review"]}, "count": {"$sum": 1}}}],
        }}]))[0]
        totals = rows["totals"][0] if rows["totals"] else {"total": 0, "average_rating": None, "unread_count": 0}
        return {**{key: value for key, value in totals.items() if key != "_id"}, **{
            key: {item["_id"]: item["count"] for item in rows[key]} for key in ("statuses", "sentiments", "decisions")}}


router = APIRouter()


@router.post("/customer-feedback", response_model=SubmissionResult)
def submit_feedback(payload: CustomerSubmission, request: Request):
    return request.app.state.cases.submit(payload, request.app.state.predictor)


@router.get("/colleague/feedback-cases", response_model=CasePage)
def list_cases(request: Request, store_id: str | None = None, status: CaseStatus | None = None,
               search: str = Query(default="", max_length=200), decision: Decision | None = None,
               page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)):
    return request.app.state.cases.list(store_id, status, search, decision, page, page_size)


@router.get("/colleague/feedback-cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: UUID, request: Request):
    return request.app.state.cases.detail(str(case_id))


@router.patch("/colleague/feedback-cases/{case_id}", response_model=CaseDetail)
def update_case(case_id: UUID, payload: CaseUpdate, request: Request):
    return request.app.state.cases.mutate(str(case_id), payload, "Colleague decision recorded")


@router.get("/colleague/notifications", response_model=Notifications)
def get_notifications(request: Request):
    return request.app.state.cases.notifications()


@router.patch("/colleague/notifications/{case_id}/read", response_model=Notifications)
def read_notification(case_id: UUID, request: Request):
    return request.app.state.cases.mark_read(str(case_id))


@router.post("/colleague/feedback-cases/{case_id}/notify-customer", response_model=CaseDetail)
def notify_customer(case_id: UUID, payload: CommunicationRequest, request: Request):
    return request.app.state.cases.mutate(str(case_id), payload, "Customer communication recorded")


@router.get("/colleague/insights", response_model=Insights)
def get_insights(request: Request, store_id: str | None = None):
    return request.app.state.cases.insights(store_id)


@router.websocket("/colleague/events")
async def case_events(websocket: WebSocket):
    import asyncio
    from starlette.concurrency import run_in_threadpool
    from pymongo.errors import PyMongoError

    origin = websocket.headers.get("origin")
    allowed = os.environ.get("FEEDBACK_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174").split(",")
    if origin and origin not in allowed:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    revision = None
    try:
        while True:
            current = await run_in_threadpool(websocket.app.state.cases.revision)
            if current != revision:
                await websocket.send_json({"type": "cases_changed", "revision": current})
                revision = current
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=1)
                if message == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                pass
    except (WebSocketDisconnect, RuntimeError, PyMongoError):
        return