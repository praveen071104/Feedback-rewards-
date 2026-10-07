"""Dependencies for FastAPI routes."""
from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.config import settings
from app.llm.base import BaseAI
from app.services import auth as auth_service


def get_ai(request: Request) -> BaseAI:
    return request.app.state.ai


def _session_token(request: Request) -> str | None:
    return request.cookies.get(settings.session_cookie_name)


def current_staff(request: Request) -> dict:
    user = auth_service.current_user(_session_token(request))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Staff login required.")
    return user
