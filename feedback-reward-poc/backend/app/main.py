"""FastAPI entry point."""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth as auth_api
from app.api import customer as customer_api
from app.api import staff as staff_api
from app.config import settings
from app.db import mongo
from app.llm.factory import ai_from_policy

log = logging.getLogger("feedback")


def _load_policy() -> dict:
    if settings.policy_path.exists():
        return json.loads(settings.policy_path.read_text(encoding="utf-8"))
    return {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo.ensure_indexes()
    app.state.policy = _load_policy()
    app.state.ai = ai_from_policy(app.state.policy, cache_path=settings.ai_cache_path)
    log.info("LLM backend: %s (model=%s)", settings.llm_backend, app.state.ai.model)
    try:
        yield
    finally:
        try:
            app.state.ai.close()
        finally:
            mongo.close()


app = FastAPI(title="M&S Feedback Rewards POC", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(auth_api.router)
app.include_router(customer_api.router)
app.include_router(staff_api.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "llm_backend": settings.llm_backend, "model": app.state.ai.model}
