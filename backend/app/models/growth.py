"""Go-to-market counters: one number per kind per day. Counts only, no personal
data and no IP addresses. Kinds in use:

* ``partner_click:<partner>``: clicks on a referral partner card (micro1, Mercor)
* ``plan:upgraded``, ``plan:cancelled``, ``plan:payment_failed``: Stripe events
* ``alerts:unsubscribed``: job alert emails turned off from an email link
"""
from datetime import date

from sqlalchemy import Column, Date, Integer, String, UniqueConstraint

from backend.app.database import Base

PARTNERS = ('micro1', 'mercor')


class GrowthCounter(Base):
    __tablename__ = 'growth_counters'
    __table_args__ = (UniqueConstraint('kind', 'day', name='uq_growth_counter_kind_day'),)

    id = Column(Integer, primary_key=True)
    kind = Column(String(60), nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)
    count = Column(Integer, nullable=False, default=0)


def bump(db, kind: str, amount: int = 1, day: date | None = None) -> None:
    """Add to today's counter. Never raises: counting must not break the action it counts."""
    try:
        day = day or date.today()
        row = db.query(GrowthCounter).filter(GrowthCounter.kind == kind, GrowthCounter.day == day).first()
        if row is None:
            db.add(GrowthCounter(kind=kind, day=day, count=amount))
        else:
            row.count = (row.count or 0) + amount
        db.commit()
    except Exception:
        db.rollback()
