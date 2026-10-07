"""Reward tier -> GBP amount lookup."""
from __future__ import annotations

from decimal import Decimal

from app.config import settings

TIER_GBP: dict[str, Decimal] = {
    "none": Decimal("0.00"),
    "low": settings.reward_low_gbp,
    "mid": settings.reward_mid_gbp,
    "high": settings.reward_high_gbp,
}


def pounds_for(tier: str) -> Decimal:
    return TIER_GBP.get(tier, Decimal("0.00")).quantize(Decimal("0.01"))
