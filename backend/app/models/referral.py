# =============================================================================
# backend/app/models/referral.py
# Referral system — tracks referrals, conversions, and earnings
# =============================================================================
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.database import Base


TIER_CONFIG = [
    {"name": "Starter",  "min": 0,  "max": 4,  "reward": 5.0},
    {"name": "Growth",   "min": 5,  "max": 14, "reward": 8.0},
    {"name": "Elite",    "min": 15, "max": None,"reward": 12.0},
]


def get_tier(total_referrals: int) -> dict:
    for tier in reversed(TIER_CONFIG):
        if total_referrals >= tier["min"]:
            return tier
    return TIER_CONFIG[0]


class Referral(Base):
    __tablename__ = "referrals"

    id              = Column(Integer, primary_key=True, index=True)
    referrer_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    referred_email  = Column(String, nullable=False)
    referred_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status          = Column(String, default="pending")     # pending | converted | paid
    plan_converted  = Column(String, nullable=True)         # pro | enterprise
    reward_amount   = Column(Float, default=0.0)
    paid_out        = Column(Boolean, default=False)
    created_at      = Column(DateTime, default=datetime.utcnow)
    converted_at    = Column(DateTime, nullable=True)

    referrer        = relationship("User", foreign_keys=[referrer_id], back_populates="referrals_made")
    referred_user   = relationship("User", foreign_keys=[referred_user_id])
