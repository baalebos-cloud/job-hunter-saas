"""Team console (Owner console tabs for product and marketing staff).

Each endpoint requires its own permission plus two-step verification
(``require_console``); none returns personal data.
"""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.roles import require_console
from backend.app.models.growth import PARTNERS, bump
from backend.app.services import growth as svc

router = APIRouter(tags=['Team console'])
track_router = APIRouter(tags=['Tracking'])


@router.get('/analytics')
def analytics(days: int = Query(30, ge=7, le=90), db: Session = Depends(get_db),
              _=Depends(require_console('analytics:read'))):
    return svc.analytics(db, days)


@router.get('/growth')
def growth(days: int = Query(30, ge=7, le=365), db: Session = Depends(get_db),
           _=Depends(require_console('growth:read'))):
    return svc.growth(db, days)


@router.get('/growth.csv')
def growth_csv(days: int = Query(30, ge=7, le=365), db: Session = Depends(get_db),
               _=Depends(require_console('growth:read'))):
    out = io.StringIO()
    csv.writer(out).writerows(svc.growth_csv_rows(svc.growth(db, days)))
    return Response(out.getvalue(), media_type='text/csv',
                    headers={'Content-Disposition': f'attachment; filename="baalebos-growth-{days}d.csv"'})


@router.get('/campaigns')
def campaigns(days: int = Query(90, ge=7, le=365), db: Session = Depends(get_db),
              _=Depends(require_console('campaigns:read'))):
    return svc.campaigns(db, days)


@router.get('/content')
def content(db: Session = Depends(get_db), _=Depends(require_console('content:read'))):
    return svc.content(db)


class PartnerClick(BaseModel):
    partner: str = Field(..., max_length=40)


@track_router.post('/partner-click', status_code=204)
def partner_click(body: PartnerClick, request: Request, db: Session = Depends(get_db)):
    """Count one click on a referral partner card. Counts only: nothing about the visitor is stored."""
    if body.partner not in PARTNERS:
        raise HTTPException(404, 'Unknown partner.')
    from backend.app.core.client_ip import client_ip
    from backend.app.core.rate_limit import hit
    allowed, _ = hit(f'partner-click:{client_ip(request)}:{body.partner}', 10, 3600)   # one person cannot inflate it
    if allowed:
        bump(db, f'partner_click:{body.partner}')
    return Response(status_code=204)
