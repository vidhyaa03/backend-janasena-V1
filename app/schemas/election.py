from pydantic import BaseModel
from datetime import datetime, date, time
from typing import Optional
 
 
from pydantic import BaseModel
from datetime import datetime, date, time
 
 
class ElectionCreate(BaseModel):
    title: str
    assembly_id: int
 
    nomination_start: datetime
    nomination_end: datetime
 
    voting_start: datetime
    voting_end: datetime
 
 
 
class ElectionResponse(BaseModel):
    id: int
    name: str
    election_level: str
    status: str
 
    district: Optional[str]
    assembly: Optional[str]
    ward: Optional[str]
 
    polling_date: Optional[date]
    polling_start_time: Optional[time]
    polling_end_time: Optional[time]
 
    total_eligible_voters: int
 
    class Config:
        from_attributes = True
 
 
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, model_validator
from datetime import datetime
from typing import Optional
 
 
class ElectionCreateByScope(BaseModel):
    title: str
 
    assembly_id: Optional[int] = None
    mandal_id: Optional[int] = None
    village_id: Optional[int] = None
    ward_id: Optional[int] = None
 
    nomination_start: datetime
    nomination_end: datetime
    voting_start: datetime
    voting_end: datetime
 
    @model_validator(mode="after")
    def validate_hierarchy(self):
        # must start with assembly
        if not self.assembly_id:
            raise ValueError("assembly_id is required")
 
        # cannot give village without mandal
        if self.village_id and not self.mandal_id:
            raise ValueError("mandal_id required when village_id is provided")
 
        # cannot give ward without village
        if self.ward_id and not self.village_id:
            raise ValueError("village_id required when ward_id is provided")
 
        return self
 