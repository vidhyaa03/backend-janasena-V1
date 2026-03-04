from pydantic import BaseModel
from typing import Optional
 
 
class ResultPublishRequest(BaseModel):
    district_id: Optional[int] = None
    assembly_id: Optional[int] = None
    mandal_id: Optional[int] = None
    village_id: Optional[int] = None
    ward_id: Optional[int] = None
 
 
 
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
 
 
# -------------------------------------------------
# 🔹 Query Params Schema
# -------------------------------------------------
 
class ResultFilterQuery(BaseModel):
    assembly_id: Optional[int] = None
    mandal_id: Optional[int] = None
    village_id: Optional[int] = None
    ward_id: Optional[int] = None
    
 
 
# -------------------------------------------------
# 🔹 Candidate Response
# -------------------------------------------------
 
class CandidateResultResponse(BaseModel):
    name: str
    votes: int
    is_winner: bool
 
 
# -------------------------------------------------
# 🔹 Election Result Response
# -------------------------------------------------
 
class ElectionResultResponse(BaseModel):
    election_id: int
    title: str
    ward_id: int
    winner_name: str
    winner_votes: int
    total_votes: int
    percentage: float
    result_published_at: Optional[datetime]
    candidates: List[CandidateResultResponse]
 
 
# -------------------------------------------------
# 🔹 Pagination Response
# -------------------------------------------------
 
class PaginationResponse(BaseModel):
    page: int
    limit: int
    total: int
    pages: int
 
 
# -------------------------------------------------
# 🔹 Final API Response
# -------------------------------------------------
 
class ResultListResponse(BaseModel):
    items: List[ElectionResultResponse]
    pagination: PaginationResponse
 