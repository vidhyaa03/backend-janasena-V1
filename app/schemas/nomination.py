from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
 
 
# -------------------------------------------------
# 🔹 Query Filter Schema
# -------------------------------------------------
 
class NominationFilterQuery(BaseModel):
    assembly_id: Optional[int] = None
    mandal_id: Optional[int] = None
    village_id: Optional[int] = None
    ward_id: Optional[int] = None
    status: Optional[str] = None
    
 
 
# -------------------------------------------------
# 🔹 Election Info
# -------------------------------------------------
 
class ElectionInfo(BaseModel):
    election_id: int
    title: str
    status: str
 
 
# -------------------------------------------------
# 🔹 Nomination Response
# -------------------------------------------------
 
class NominationResponse(BaseModel):
    nomination_id: int
    candidate_id: Optional[int]
    member_id: int
    member_name: Optional[str]
    mobile: Optional[str]
    photo_url: Optional[str]
    location: Optional[str]
    applied_at: Optional[datetime]
    reviewed_at: Optional[datetime]
    rejection_reason: Optional[str]
    election: Optional[ElectionInfo]
 
 
 
# -------------------------------------------------
# 🔹 Pagination
# -------------------------------------------------

 
 
class PaginationResponse(BaseModel):
    page: int
    limit: int
    total: int
    pages: int
 
 
# -------------------------------------------------
# 🔹 Final Response
# -------------------------------------------------
 
class NominationListResponse(BaseModel):
    items: List[NominationResponse]
    pagination: PaginationResponse
 