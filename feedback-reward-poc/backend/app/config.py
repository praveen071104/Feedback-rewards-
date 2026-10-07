"""Environment-driven configuration for the Feedback Rewards POC.

AI knobs live in `policy.json` (see `ai_from_policy`), matching the reference
project. The only AI-related env var here is the backend toggle.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- MongoDB (document store) ----
    mongodb_uri: str = Field(default="mongodb://127.0.0.1:27017", alias="MONGODB_URI")
    mongodb_database: str = Field(default="ms_feedback_platform", alias="MONGODB_DATABASE")

    # ---- LLM backend toggle (teammate uses CTL_AI; we use LLM_BACKEND) ----
    llm_backend: str = Field(default="scripted", alias="LLM_BACKEND")  # scripted | copilot
    policy_path: Path = Field(default=BACKEND_ROOT / "policy.json", alias="FEEDBACK_POLICY_PATH")
    ai_cache_path: Path = Field(default=BACKEND_ROOT / "data" / "ai_cache.json", alias="FEEDBACK_AI_CACHE_PATH")

    # ---- Reward tiers (GBP) ----
    reward_low_gbp: Decimal = Field(default=Decimal("2.00"), alias="FEEDBACK_REWARD_LOW_GBP")
    reward_mid_gbp: Decimal = Field(default=Decimal("3.50"), alias="FEEDBACK_REWARD_MID_GBP")
    reward_high_gbp: Decimal = Field(default=Decimal("5.00"), alias="FEEDBACK_REWARD_HIGH_GBP")

    # ---- CORS ----
    allowed_origins: list[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        alias="FEEDBACK_ALLOWED_ORIGINS",
    )

    # ---- Session ----
    session_cookie_name: str = Field(default="feedback_staff_session", alias="FEEDBACK_SESSION_COOKIE")
    session_cookie_secure: bool = Field(default=False, alias="FEEDBACK_COOKIE_SECURE")
    session_ttl_hours: int = Field(default=8, alias="FEEDBACK_SESSION_TTL_HOURS")


settings = Settings()
