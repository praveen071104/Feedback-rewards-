"""Pydantic request/response models for the HTTP layer."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


StoreId = Literal["marble-arch", "stratford-city", "bluewater", "unspecified"]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class FeedbackSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    store_id: StoreId = "unspecified"
    stars: int = Field(ge=1, le=5)
    feedback: str = Field(min_length=1, max_length=5000)
    sparks_member: bool = False
    sparks_id: str | None = Field(default=None, max_length=40)
    submission_id: UUID = Field(default_factory=uuid4)

    @field_validator("email")
    @classmethod
    def _email_shape(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("Email must look like name@domain.tld.")
        return v

    @field_validator("feedback")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Feedback must not be empty.")
        return v

    @field_validator("sparks_id")
    @classmethod
    def _sparks_shape(cls, v: str | None) -> str | None:
        if v is None:
            return None
        digits = re.sub(r"[\s-]", "", v)
        if not digits:
            return None
        if not re.fullmatch(r"\d{16}", digits):
            raise ValueError("Sparks card number must be exactly 16 digits.")
        return digits

    @model_validator(mode="after")
    def _sparks_consistency(self):
        if self.sparks_member and not self.sparks_id:
            raise ValueError("Please enter your 16-digit Sparks card number, or untick the Sparks member box.")
        if not self.sparks_member:
            self.sparks_id = None
        return self


class RewardOut(BaseModel):
    tier: Literal["none", "low", "mid", "high"]
    amount_gbp: float
    status: Literal["awaiting_eligibility_review"]


class RewardQueueItem(BaseModel):
    id: int
    submission_id: UUID
    customer_name: str | None = None
    customer_email: str | None = None
    store_id: str | None = None
    stars: int | None = None
    sparks_member: bool | None = None
    sparks_id: str | None = None
    feedback: str | None = None
    category: str | None = None
    aspects: list[dict] = []
    tier: Literal["low", "mid", "high"]
    amount_gbp: float
    status: Literal["issued"]
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_note: str | None = None
    issued_at: datetime


class RewardEligibilityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tier: Literal["none", "low", "mid", "high"]
    note: str | None = Field(default=None, max_length=500)


class RewardEligibilityOut(BaseModel):
    submission_id: str
    suggested_tier: Literal["none", "low", "mid", "high"]
    suggested_amount_gbp: float
    tier: Literal["none", "low", "mid", "high"] | None = None
    eligible: bool | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    note: str | None = None


class TicketOut(BaseModel):
    id: int
    submission_id: UUID
    category: str
    priority: Literal["low", "medium", "high"]
    status: Literal["open", "in_progress", "resolved"]
    assignee: str | None
    store_id: str | None
    customer_name: str | None
    customer_email: str | None
    summary: str
    opened_at: datetime
    closed_at: datetime | None
    resolution_notes: str | None


class TicketEventOut(BaseModel):
    id: int
    event_type: str
    actor: str
    note: str | None
    created_at: datetime


class TicketDetailOut(TicketOut):
    events: list[TicketEventOut]
    customer_reply: str | None = None
    reward_followup: str | None = None
    feedback: str | None = None
    stars: int | None = None
    sparks_member: bool | None = None
    sparks_id: str | None = None
    aspects: list[dict] | None = None
    overall_sentiment: str | None = None
    overall_score: float | None = None


class FeedbackSubmissionResult(BaseModel):
    submission_id: UUID
    category: str
    customer_reply: str
    reward_followup: str | None = None
    reward: RewardOut
    ticket_id: int | None = None
    needs_more_detail: bool = False


class TicketUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["open", "in_progress", "resolved"] | None = None
    assignee: str | None = Field(default=None, max_length=120)
    resolution_notes: str | None = Field(default=None, max_length=2000)
    note: str | None = Field(default=None, max_length=2000)


class StaffLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=60)
    password: str = Field(min_length=12, max_length=200)


class StaffSetup(StaffLogin):
    pass


class AuthStatus(BaseModel):
    setup_required: bool
    authenticated: bool
    username: str | None = None


class InsightsOut(BaseModel):
    total_feedback: int
    by_category: dict[str, int]
    by_store: dict[str, int]
    open_tickets: int
    resolved_tickets: int
    total_rewards_issued: int
    total_gbp_issued: float
    has_more_recent: bool = False
    recent: list[dict]
