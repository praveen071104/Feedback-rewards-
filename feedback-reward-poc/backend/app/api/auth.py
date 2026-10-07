"""Staff authentication endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.config import settings
from app.models.schemas import AuthStatus, StaffLogin, StaffSetup
from app.services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _cookie_kwargs() -> dict:
    return {
        "httponly": True,
        "samesite": "strict",
        "secure": settings.session_cookie_secure,
        "path": "/",
    }


@router.get("/status", response_model=AuthStatus)
def status_(request: Request) -> AuthStatus:
    token = request.cookies.get(settings.session_cookie_name)
    user = auth_service.current_user(token)
    return AuthStatus(
        setup_required=auth_service.setup_required(),
        authenticated=user is not None,
        username=user["username"] if user else None,
    )


@router.post("/setup")
def setup(payload: StaffSetup, response: Response) -> dict:
    try:
        user = auth_service.create_first_admin(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    result = auth_service.login(payload.username, payload.password)
    if result is None:
        raise HTTPException(status_code=500, detail="Setup succeeded but login failed.")
    token, expires_at = result
    response.set_cookie(settings.session_cookie_name, token, expires=expires_at, **_cookie_kwargs())
    return {"username": user["username"]}


@router.post("/login")
def login(payload: StaffLogin, response: Response) -> dict:
    result = auth_service.login(payload.username, payload.password)
    if result is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    token, expires_at = result
    response.set_cookie(settings.session_cookie_name, token, expires=expires_at, **_cookie_kwargs())
    return {"username": payload.username}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(settings.session_cookie_name)
    auth_service.logout(token)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return {"ok": True}
