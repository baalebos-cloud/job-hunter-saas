# =============================================================================
# backend/app/models/subscription.py
# =============================================================================
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.database import Base


PLANS = {
    "free":       {"name": "Free",       "price": 0,  "scans_per_month": 2},
    "pro":        {"name": "Pro",        "price": 19, "scans_per_month": -1},  # -1 = unlimited
    "enterprise": {"name": "Enterprise", "price": 49, "scans_per_month": -1},
}


class Subscription(Base):
    __tablename__ = "subscriptions"

    id                  = Column(Integer, primary_key=True, index=True)
    user_id             = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    plan                = Column(String, default="free")          # free | pro | enterprise
    stripe_customer_id  = Column(String, nullable=True)
    stripe_sub_id       = Column(String, nullable=True)
    status              = Column(String, default="active")        # active | cancelled | past_due
    scans_this_month    = Column(Integer, default=0)
    reset_date          = Column(DateTime, default=datetime.utcnow)
    created_at          = Column(DateTime, default=datetime.utcnow)
    updated_at          = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="subscription")
