import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from predict import FeedbackPredictor


@asynccontextmanager
async def lifespan(application: FastAPI):
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

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, value: str) -> str:
        value = value.strip()
        if not value or not any(character.isalpha() for character in value):
            raise ValueError("Feedback must contain at least one letter")
        return value


class PredictionResponse(BaseModel):
    sentiment: Literal["Positive", "Neutral", "Negative"]
    sentimentConfidence: float = Field(ge=0, le=1)
    genuineFeedback: Literal["Yes", "No"]
    genuineConfidence: float = Field(ge=0, le=1)
    rewardEligible: bool
    reason: str


@app.get("/health")
def health(request: Request):
    ready = request.app.state.predictor is not None
    return {"status": "ready" if ready else "models_missing", "modelsLoaded": ready}


@app.post("/predict", response_model=PredictionResponse)
def predict_feedback(payload: FeedbackRequest, request: Request):
    predictor = request.app.state.predictor
    if predictor is None:
        raise HTTPException(503, "Models unavailable. Train both models and restart the API.")
    return predictor.predict(payload.feedback)