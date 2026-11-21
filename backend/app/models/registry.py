"""Import every model module so Base.metadata is complete (Alembic, scripts)."""


def import_all_models():
    from backend.app.models import (application, automation, job, referral, resume,  # noqa: F401
                                    security, security_event, subscription, support, user)
    try:
        from backend.app.models import audit  # noqa: F401
    except ImportError:
        pass
    from backend.app.database import Base
    return Base.metadata
