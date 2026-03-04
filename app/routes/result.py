from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
 
from app.core.database import get_db
from app.middleware.auth import get_current_admin
from app.schemas.result import ResultPublishRequest
from app.models.models import Admin
from app.services.result_service import get_results_by_scope
from app.services.result_service import admin_unpublish_election_result
router = APIRouter(
    prefix="/results",
    tags=["Results"],
   
)
 
 
 
@router.get("/admin/all")
async def admin_get_all_results_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Results per page"),
    state_id: Optional[int] = Query(None, description="Filter by state ID"),
    district_id: Optional[int] = Query(None, description="Filter by district ID"),
    assembly_id: Optional[int] = Query(None, description="Filter by assembly ID"),
    election_level: Optional[str] = Query(None, description="Filter by election level"),
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
   
    from app.services.result_service import admin_get_all_results, AdminResultsFilterParams
   
    filters = AdminResultsFilterParams(
        page=page,
        limit=limit,
        state_id=state_id,
        district_id=district_id,
        assembly_id=assembly_id,
        election_level=election_level,
    )
 
    result = await admin_get_all_results(db, admin.admin_id, filters)
    return result
 
 
 
 
 
@router.get("/admin/assembly/{assembly_id}")
async def admin_get_results_by_assembly_endpoint(
    assembly_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Results per page"),
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
   
    from app.services.result_service import admin_get_results_by_assembly
   
    result = await admin_get_results_by_assembly(
        db, admin.admin_id, assembly_id, page, limit
    )
 
    if not result.get("items") and result.get("pagination", {}).get("total") == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No results found for this assembly",
        )
 
    return result
 
 
# =========================================================
# ADMIN ONLY - DASHBOARD STATS
# =========================================================
 
 
 
 
@router.post("/admin/publish/{election_id}")
async def admin_publish_single_election(
    election_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
   
    from app.services.result_service import admin_publish_election_result
   
    result = await admin_publish_election_result(db, admin.admin_id, election_id)
 
    if result.get("status") == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("error"),
        )
    elif result.get("status") == 403:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=result.get("error"),
        )
    elif result.get("status") == 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error"),
        )
 
    return result
 
 
 
 
@router.post("/admin/unpublish/{election_id}")
async def admin_unpublish_single_election(
    election_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
   
   
   
    result = await admin_unpublish_election_result(db, admin.admin_id, election_id)
 
    if result.get("status") == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("error"),
        )
    elif result.get("status") == 403:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=result.get("error"),
        )
    elif result.get("status") == 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error"),
        )
 
    return result
 
 
 
@router.get("/filter")
async def fetch_results(
    assembly_id: Optional[int] = Query(None),
    mandal_id: Optional[int] = Query(None),
    village_id: Optional[int] = Query(None),
    ward_id: Optional[int] = Query(None),
    
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    return await get_results_by_scope(
        db,
        assembly_id,
        mandal_id,
        village_id,
        ward_id,
        page,
        limit,
    )
 
 
 