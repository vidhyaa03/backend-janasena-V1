from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.election import ElectionCreate
from app.core.database import get_db
from app.schemas.election import ElectionCreate
from app.services.election_service import create_election, get_elections , create_election_by_scope , get_elections_by_scope
from app.middleware.auth import get_current_admin
from app.models.models import Admin
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
 
from app.services.results import calculate_election_winner
 
router = APIRouter(
    prefix="/elections",
    tags=["Elections"],
    dependencies=[Depends(get_current_admin)],  #  Protect ALL election APIs
)
 
@router.post("/admin/calculate-result/{election_id}")
async def calculate_result(
    election_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await calculate_election_winner(db, election_id)
# ========= POST =========
@router.post("/")
async def create_new_election(
    data: ElectionCreate,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),  # Get real admin from JWT
):
    """
    Create election using logged-in admin
    """
    return await create_election(db, data, admin.admin_id)
 
 
# ========= GET =========
@router.get("/")
async def list_elections(
    status: str | None = Query(
        default=None,
        description="DRAFT | SCHEDULED | ACTIVE | COMPLETED",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns:
    - All elections if no status
    - Filtered elections if status provided
    """
    return await get_elections(db, status)
 
from app.schemas.election import ElectionCreateByScope
 
@router.post("/by-scope")
async def create_election_scope(
    data: ElectionCreateByScope,   #
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    """
    Create election by Assembly / Mandal / Village / Ward scope
    """
    return await create_election_by_scope(db, data, admin.admin_id)
 
 
@router.get("/filter")
async def fetch_elections(
    assembly_id: int | None = None,
    mandal_id: int | None = None,
    village_id: int | None = None,
    ward_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await get_elections_by_scope(
        db,
        assembly_id,
        mandal_id,
        village_id,
        ward_id,
    )
 