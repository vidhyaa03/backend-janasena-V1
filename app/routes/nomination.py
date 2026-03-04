from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
 
from app.core.database import get_db
from app.services.nomination_service import create_nomination_notification
 
from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession
 
from app.core.database import get_db
from app.middleware.auth import get_current_admin
from app.services.nomination_service import (
    get_all_nominations,
    approve_nomination,
    reject_nomination,
)
 
 
router = APIRouter(prefix="/nominations", tags=["Nominations"])
 
 
 
@router.post("/{event_id}")
async def send_nomination_notification(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    """
    Admin triggers nomination notification for an ElectionEvent.
    """
    try:
        return await create_nomination_notification(
            db=db,
            event_id=event_id,
            admin_id=current_admin.admin_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
 
 
 
 
 
@router.get("/")
async def list_nominations(
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return await get_all_nominations(db)
 
 
# ==============================
# Approve nomination
# ==============================
@router.post("/{nomination_id}/approve")
async def approve(
    nomination_id: int,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return await approve_nomination(db, nomination_id, admin.admin_id)
 
 
# ==============================
# Reject nomination
# ==============================
@router.post("/{nomination_id}/reject")
async def reject(
    nomination_id: int,
    reason: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return await reject_nomination(db, nomination_id, admin.admin_id, reason)
 
 
from fastapi import APIRouter, Depends, Query
 
from typing import Optional
 
 
from app.models.models import Admin
from app.services.nomination_service import get_nominations_by_scope
 
 
 
@router.get("/filter")
async def list_nominations_by_scope(
    assembly_id: Optional[int] = Query(None),
    mandal_id: Optional[int] = Query(None),
    village_id: Optional[int] = Query(None),
    ward_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),  # 🔐 Admin Protected
):
    return await get_nominations_by_scope(
        db,
        assembly_id,
        mandal_id,
        village_id,
        ward_id
    )
 