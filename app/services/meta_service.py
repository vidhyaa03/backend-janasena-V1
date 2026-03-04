from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
 
from app.models.models import (
    NotificationType, State, Assembly, Village, Mandal
)
from app.models.models import Ward, Village, Mandal
 
 
#All Notification Types
async def get_notification_types():
    return [t.value for t in NotificationType]
 
 
# All States
async def get_states(db: AsyncSession):
    result = await db.execute(select(State.state_id, State.state_name))
    return [{"id": s.state_id, "name": s.state_name} for s in result.all()]
 
 
#  All Assemblies (no district filter)
async def get_all_assemblies(db: AsyncSession):
    result = await db.execute(select(Assembly.assembly_id, Assembly.assembly_name))
    return [{"id": a.assembly_id, "name": a.assembly_name} for a in result.all()]
 
 
#  Villages by Assembly (IMPORTANT CHANGE)
async def get_villages_by_assembly(db: AsyncSession, assembly_id: int):
    result = await db.execute(
        select(
            Village.village_id,
            Village.village_name,
            Mandal.mandal_id,
            Mandal.mandal_name
        )
        .join(Mandal, Village.mandal_id == Mandal.mandal_id)
        .where(Mandal.assembly_id == assembly_id)
    )
 
    return [
        {
            "village_id": v.village_id,
            "village_name": v.village_name,
            "mandal_id": v.mandal_id,
            "mandal_name": v.mandal_name,
        }
        for v in result.all()
    ]
 
 
 
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
 
from app.models.models import ElectionEvent, Election
 
 
async def get_all_events_with_elections(db: AsyncSession):
    """
    Returns:
    - event_id
    - event_title
    """
 
    try:
        result = await db.execute(
            select(ElectionEvent, Election)
            .join(Election, Election.event_id == ElectionEvent.event_id, isouter=True)
            .order_by(ElectionEvent.event_id.desc())
        )
 
        rows = result.all()
        events_map = {}
 
        for event, election in rows:
 
            if event.event_id not in events_map:
                events_map[event.event_id] = {
                    "event_id": event.event_id,
                    "event_title": event.title,
                }
 
        return {
            "total_events": len(events_map),
            "events": list(events_map.values()),
        }
 
    #  Database error
    except SQLAlchemyError as e:
        await db.rollback()
        raise Exception("Database error while fetching events")
 
    #  Any unexpected error
    except Exception as e:
        raise Exception("Something went wrong while fetching events")
   
 
 
 
 
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
 
from app.models.models import Mandal, Village, Ward
 
 
async def get_mandals_villages_with_ward_count(db: AsyncSession, assembly_id: int):
    """
    Returns ALL mandals of an assembly,
    including mandals with:
    - no villages
    - villages with no wards
    """
 
    result = await db.execute(
        select(
            Mandal.mandal_id,
            Mandal.mandal_name,
            Village.village_id,
            Village.village_name,
            func.count(Ward.ward_id).label("ward_count")
        )
        .outerjoin(Village, Village.mandal_id == Mandal.mandal_id)   # ← FIXED
        .outerjoin(Ward, Ward.village_id == Village.village_id)
        .where(Mandal.assembly_id == assembly_id)
        .group_by(
            Mandal.mandal_id,
            Mandal.mandal_name,
            Village.village_id,
            Village.village_name
        )
        .order_by(Mandal.mandal_id, Village.village_id)
    )
 
    rows = result.all()
 
    mandals_map = {}
 
    for row in rows:
        mandal_id = row.mandal_id
 
        if mandal_id not in mandals_map:
            mandals_map[mandal_id] = {
                "mandal_id": row.mandal_id,
                "mandal_name": row.mandal_name,
                "villages": []
            }
 
        # Only append village if it exists
        if row.village_id is not None:
            mandals_map[mandal_id]["villages"].append({
                "village_id": row.village_id,
                "village_name": row.village_name,
                "ward_count": row.ward_count
            })
 
    return list(mandals_map.values())
 
 
 
 
async def get_wards_by_location(
    db: AsyncSession,
    assembly_id: int,
    mandal_id: int,
    village_id: int
):
    """
    Returns wards filtered by:
    assembly_id + mandal_id + village_id
    """
 
    result = await db.execute(
        select(
            Ward.ward_id,
            Ward.ward_number,
            Ward.ward_name,
            Village.village_id,
            Village.village_name,
            Mandal.mandal_id,
            Mandal.mandal_name
        )
        .join(Village, Ward.village_id == Village.village_id)
        .join(Mandal, Village.mandal_id == Mandal.mandal_id)
        .where(
            Mandal.assembly_id == assembly_id,
            Mandal.mandal_id == mandal_id,
            Village.village_id == village_id
        )
        .order_by(Ward.ward_number)
    )
 
    rows = result.all()
 
    return [
        {
            "ward_id": r.ward_id,
            "ward_number": r.ward_number,
            "ward_name": r.ward_name,
            "village_id": r.village_id,
            "village_name": r.village_name,
            "mandal_id": r.mandal_id,
            "mandal_name": r.mandal_name,
        }
        for r in rows
    ]
 