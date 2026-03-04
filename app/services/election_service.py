from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from datetime import datetime
import pytz
 
from app.models.models import (
    Election, ElectionEvent, Ward, Village, Mandal, Assembly, District, Member
)
 
 
 
 
 
IST = pytz.timezone("Asia/Kolkata")
 
 
# =========================================================
# CREATE ELECTION (PURE IST)
# =========================================================
async def create_election(db: AsyncSession, data, admin_id: int):
   
 
    # -------------------------------------------------
    # 1️⃣ Find wards in assembly
    # -------------------------------------------------
    ward_query = (
        select(Ward)
        .join(Village, Ward.village_id == Village.village_id)
        .join(Mandal, Village.mandal_id == Mandal.mandal_id)
        .where(Mandal.assembly_id == data.assembly_id)
    )
 
    wards = (await db.execute(ward_query)).scalars().all()
 
    if not wards:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No wards found for this assembly"
        )
 
    # -------------------------------------------------
    # 2️⃣ KEEP IST AS-IS (NO CONVERSION)
    # -------------------------------------------------
    nomination_start = data.nomination_start.replace(tzinfo=None)
    nomination_end   = data.nomination_end.replace(tzinfo=None)
    voting_start     = data.voting_start.replace(tzinfo=None)
    voting_end       = data.voting_end.replace(tzinfo=None)
 
    # -------------------------------------------------
    # 3️⃣ VALIDATION (important in production)
    # -------------------------------------------------
    if not (nomination_start < nomination_end < voting_start < voting_end):
        raise HTTPException(
            status_code=400,
            detail="Invalid election timeline order"
        )
 
    # -------------------------------------------------
    # 4️⃣ Create ElectionEvent
    # -------------------------------------------------
    event = ElectionEvent(
        assembly_id=data.assembly_id,
        title=data.title,
        nomination_start=nomination_start,
        nomination_end=nomination_end,
        voting_start=voting_start,
        voting_end=voting_end,
    )
 
    db.add(event)
    await db.flush()
 
    # -------------------------------------------------
    # 5️⃣ Create ward elections
    # -------------------------------------------------
    for ward in wards:
        db.add(Election(
            event_id=event.event_id,
            title=data.title,
            ward_id=ward.ward_id,
            admin_id=admin_id,
            election_level="WARD",
            status="SCHEDULED",
        ))
 
    await db.commit()
 
    return {
        "message": "Election event and ward elections created",
        "event_id": event.event_id,
        "total_wards": len(wards),
    }
 
 
# =========================================================
# GET ELECTIONS (PURE IST RETURN)
# =========================================================
from sqlalchemy import select, func
 
 
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
 
from app.models.models import (
    Election, ElectionEvent, Ward, Village, Mandal, Assembly, District, Member
)
 
async def get_elections(db: AsyncSession, status: str | None = None):
    """
    Returns election list with:
    - total voters in ward
    - total votes polled
    - Combined geographical location string
    """
 
    voters_subq = (
        select(
            Member.ward_id,
            func.count(Member.member_id).label("total_voters")
        )
        .where(Member.is_eligible_to_vote == True)
        .group_by(Member.ward_id)
        .subquery()
    )
 
    query = (
        select(
            Election,
            ElectionEvent,
            Ward,
            Village,
            Mandal,
            Assembly,
            District,
            voters_subq.c.total_voters,
        )
        .join(ElectionEvent, Election.event_id == ElectionEvent.event_id)
        .join(Ward, Election.ward_id == Ward.ward_id)
        .join(Village, Ward.village_id == Village.village_id)
        .join(Mandal, Village.mandal_id == Mandal.mandal_id)
        .join(Assembly, Mandal.assembly_id == Assembly.assembly_id)
        .join(District, Assembly.district_id == District.district_id)
        .outerjoin(voters_subq, voters_subq.c.ward_id == Ward.ward_id)
        .order_by(Election.created_at.desc())
    )
 
    if status:
        query = query.where(Election.status == status.upper())
 
    rows = (await db.execute(query)).all()
 
    elections = []
 
    for e, ev, w, v, m, a, d, total_voters in rows:
 
        # ⭐ Combined readable location
        location = f"{w.ward_name}, {v.village_name}, {a.assembly_name}, {d.district_name}"
 
        elections.append({
            "event_id": ev.event_id,
            "election_id": e.election_id,
            "title": ev.title,
            "status": e.status,
 
            # ⭐ Single combined field
            "location": location,
 
            # Optional → keep ward_id for frontend routing
            "ward_id": w.ward_id,
 
            # Counts
            "total_voters": total_voters or 0,
            "total_votes_polled": e.total_votes,
 
            # Result flags
            "result_calculated": e.result_calculated,
            "result_published": e.result_published,
 
            #Schedule
            "nomination_start": ev.nomination_start,
            "nomination_end": ev.nomination_end,
            "voting_start": ev.voting_start,
            "voting_end": ev.voting_end,
 
            "created_at": e.created_at,
        })
 
    return elections
 
async def create_election_by_scope(db: AsyncSession, data, admin_id: int):
    """
    Create elections dynamically based on selected scope:
    - assembly_id
    - mandal_id
    - village_id
    - ward_id
    """
 
    # -------------------------------------------------
    # 1️⃣ Decide ward query based on scope
    # -------------------------------------------------
    ward_query = select(Ward)
 
    if data.ward_id:
        ward_query = ward_query.where(Ward.ward_id == data.ward_id)
 
    elif data.village_id:
        ward_query = ward_query.where(Ward.village_id == data.village_id)
 
    elif data.mandal_id:
        ward_query = ward_query.join(Village).where(
            Village.mandal_id == data.mandal_id
        )
 
    elif data.assembly_id:
        ward_query = (
            ward_query
            .join(Village, Ward.village_id == Village.village_id)
            .join(Mandal, Village.mandal_id == Mandal.mandal_id)
            .where(Mandal.assembly_id == data.assembly_id)
        )
 
    else:
        raise HTTPException(400, "At least one scope ID required")
 
    wards = (await db.execute(ward_query)).scalars().all()
 
    if not wards:
        raise HTTPException(404, "No wards found for selected scope")
 
    # -------------------------------------------------
    # 2️⃣ Validate timeline
    # -------------------------------------------------
    nomination_start = data.nomination_start.replace(tzinfo=None)
    nomination_end   = data.nomination_end.replace(tzinfo=None)
    voting_start     = data.voting_start.replace(tzinfo=None)
    voting_end       = data.voting_end.replace(tzinfo=None)
 
    if not (nomination_start < nomination_end < voting_start < voting_end):
        raise HTTPException(400, "Invalid election timeline")
 
    # -------------------------------------------------
    # 3️⃣ Create event
    # -------------------------------------------------
    event = ElectionEvent(
        assembly_id=data.assembly_id,
        title=data.title,
        nomination_start=nomination_start,
        nomination_end=nomination_end,
        voting_start=voting_start,
        voting_end=voting_end,
    )
 
    db.add(event)
    await db.flush()
 
    # -------------------------------------------------
    # 4️⃣ Create elections for wards
    # -------------------------------------------------
    for ward in wards:
        db.add(Election(
            event_id=event.event_id,
            title=data.title,
            ward_id=ward.ward_id,
            admin_id=admin_id,
            election_level="WARD",
            status="SCHEDULED",
        ))
 
    await db.commit()
 
    return {
        "message": "Election created based on selected scope",
        "event_id": event.event_id,
        "total_wards": len(wards),
    }
 
 
 
 
async def get_elections_by_scope(
    db: AsyncSession,
    assembly_id: int | None = None,
    mandal_id: int | None = None,
    village_id: int | None = None,
    ward_id: int | None = None,
):
    """
    Hierarchical filtered elections
    """
 
    voters_subq = (
        select(
            Member.ward_id,
            func.count(Member.member_id).label("total_voters")
        )
        .where(Member.is_eligible_to_vote == True)
        .group_by(Member.ward_id)
        .subquery()
    )
 
    query = (
        select(
            Election,
            ElectionEvent,
            Ward,
            Village,
            Mandal,
            Assembly,
            District,
            voters_subq.c.total_voters,
        )
        .join(ElectionEvent, Election.event_id == ElectionEvent.event_id)
        .join(Ward, Election.ward_id == Ward.ward_id)
        .join(Village, Ward.village_id == Village.village_id)
        .join(Mandal, Village.mandal_id == Mandal.mandal_id)
        .join(Assembly, Mandal.assembly_id == Assembly.assembly_id)
        .join(District, Assembly.district_id == District.district_id)
        .outerjoin(voters_subq, voters_subq.c.ward_id == Ward.ward_id)
        .order_by(Election.created_at.desc())
    )
 
    # -------------------------------------------------
    # APPLY HIERARCHICAL FILTERS
    # priority → ward > village > mandal > assembly
    # -------------------------------------------------
 
    if ward_id:
        query = query.where(Ward.ward_id == ward_id)
 
    elif village_id:
        query = query.where(Village.village_id == village_id)
 
    elif mandal_id:
        query = query.where(Mandal.mandal_id == mandal_id)
 
    elif assembly_id:
        query = query.where(Assembly.assembly_id == assembly_id)
 
    rows = (await db.execute(query)).all()
 
    elections = []
 
    for e, ev, w, v, m, a, d, total_voters in rows:
 
        location = f"{w.ward_name}, {v.village_name}, {a.assembly_name}, {d.district_name}"
 
        elections.append({
            "event_id": ev.event_id,
            "election_id": e.election_id,
            "title": ev.title,
            "status": e.status,
            "election_level": e.election_level,
            "location": location,
            "ward_id": w.ward_id,
            "total_voters": total_voters or 0,
            "total_votes_polled": e.total_votes,
            "result_calculated": e.result_calculated,
            "result_published": e.result_published,
            "nomination_start": ev.nomination_start,
            "nomination_end": ev.nomination_end,
            "voting_start": ev.voting_start,
            "voting_end": ev.voting_end,
            "created_at": e.created_at,
        })
 
    return elections
 