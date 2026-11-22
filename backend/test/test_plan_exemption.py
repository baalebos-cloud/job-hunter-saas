"""Verified admins and the platform owner are never limited by plan quotas."""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.dependencies.plan_guard import (
    consume_scan, is_plan_exempt, remaining_scans, require_pro, require_scan_quota)
from backend.app.models.registry import import_all_models
from backend.app.models.subscription import Subscription
from backend.app.models.user import User

from backend.app.models.subscription import PLANS as _PLANS

FREE_LIMIT = _PLANS['free']['scans_per_month']   # whatever the free plan allows


@pytest.fixture
def db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    import_all_models()
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        User(email='admin@example.com', hashed_password='x', is_admin=True, is_verified=True),
        User(email='owner@example.com', hashed_password='x', role='super_admin', is_verified=True),
        User(email='unverified-admin@example.com', hashed_password='x', is_admin=True, is_verified=False),
        User(email='candidate@example.com', hashed_password='x', is_verified=True),
    ])
    session.commit()
    for user in session.query(User).all():
        # Every account is on the free plan with this month's scans used up.
        session.add(Subscription(user_id=user.id, plan='free', status='active', scans_this_month=FREE_LIMIT))
    session.commit()
    yield session
    session.close()


def user(db, email):
    return db.query(User).filter_by(email=email).one()


def scans(db, account):
    return db.query(Subscription).filter_by(user_id=account.id).one().scans_this_month


@pytest.mark.parametrize('email', ['admin@example.com', 'owner@example.com'])
def test_verified_admin_and_owner_are_never_limited(db, email):
    account = user(db, email)
    assert is_plan_exempt(account)
    assert require_scan_quota(current_user=account, db=db) is account   # quota already used up
    assert require_pro(current_user=account, db=db) is account           # free plan
    assert remaining_scans(account.id, db) is None                       # unlimited
    consume_scan(account.id, db)
    db.commit()
    assert scans(db, account) == FREE_LIMIT                              # nothing counted


@pytest.mark.parametrize('email', ['candidate@example.com', 'unverified-admin@example.com'])
def test_other_accounts_keep_their_plan_limits(db, email):
    account = user(db, email)
    assert not is_plan_exempt(account)
    with pytest.raises(HTTPException) as quota:
        require_scan_quota(current_user=account, db=db)
    assert quota.value.status_code == 403 and quota.value.detail['error'] == 'scan_limit_reached'
    with pytest.raises(HTTPException) as pro:
        require_pro(current_user=account, db=db)
    assert pro.value.detail['error'] == 'pro_required'
    assert remaining_scans(account.id, db) == 0
    with pytest.raises(HTTPException):
        consume_scan(account.id, db)


def test_billing_status_reports_exempt_accounts_as_unlimited(db):
    from backend.app.routes.billing import get_billing_status
    owner = get_billing_status(current_user=user(db, 'owner@example.com'), db=db)
    assert owner['scans_limit'] == owner['scans_left'] == -1 and owner['is_pro'] and owner['plan_exempt']
    candidate = get_billing_status(current_user=user(db, 'candidate@example.com'), db=db)
    assert candidate['scans_limit'] == FREE_LIMIT and candidate['scans_left'] == 0
    assert not candidate['is_pro'] and not candidate['plan_exempt']
