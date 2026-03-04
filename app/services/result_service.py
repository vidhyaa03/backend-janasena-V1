from sqlalchemy import select, func, and_, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
 
from app.models.models import (
    Election,
    Candidate,
    Vote,
    Member,
    Notification,
    NotificationType,
    State,
    District,
    Assembly,
    Mandal,
    Village,
    Ward,
    Admin,
)
 
 
 
 
class AdminResultsFilterParams(BaseModel):
    """Parameters for filtering admin results"""
    page: int = 1
    limit: int = 10
    state_id: Optional[int] = None
    district_id: Optional[int] = None
    assembly_id: Optional[int] = None
    election_level: Optional[str] = None
    status: str = "COMPLETED"
 
 
 
async def get_results(
    db: AsyncSession,
    page: int,
    limit: int,
    election_level: str | None,
    district_id: int | None,
):
    """Get published election results with pagination and basic filters"""
 
    base_query = (
        select(
            Election.election_id,
            Election.title,
            Member.name.label("winner_name"),
            Candidate.vote_count,
            func.count(Vote.vote_id).label("total_votes"),
            Election.result_published_at,
        )
        .join(Candidate, Candidate.election_id == Election.election_id)
        .join(Member, Member.member_id == Candidate.member_id)
        .outerjoin(
            Vote,
            and_(
                Vote.election_id == Election.election_id,
                Vote.candidate_id == Candidate.candidate_id,
            ),
        )
        .where(
            Election.status == "COMPLETED",
            Election.result_published == True,
            Candidate.is_winner == True,
        )
        .group_by(Election.election_id, Candidate.candidate_id, Member.member_id)
        .order_by(Election.created_at.desc())
    )
 
    # Apply filters
    if election_level:
        base_query = base_query.where(Election.election_level == election_level)
   
    if district_id:
        base_query = (
            base_query
            .join(Ward, Ward.ward_id == Election.ward_id)
            .join(Village, Village.village_id == Ward.village_id)
            .join(Mandal, Mandal.mandal_id == Village.mandal_id)
            .join(Assembly, Assembly.assembly_id == Mandal.assembly_id)
            .join(District, District.district_id == Assembly.district_id)
            .where(District.district_id == district_id)
        )
 
    total = (
        await db.execute(
            select(func.count(Election.election_id.distinct())).select_from(
                select(Election.election_id)
                .join(Candidate, Candidate.election_id == Election.election_id)
                .where(
                    Election.status == "COMPLETED",
                    Election.result_published == True,
                    Candidate.is_winner == True,
                )
            )
        )
    ).scalar() or 0
 
    rows = (
        await db.execute(base_query.offset((page - 1) * limit).limit(limit))
    ).all()
 
    items = []
 
    for election_id, title, winner_name, winner_votes, total_votes, published_at in rows:
        percentage = round((winner_votes / total_votes) * 100, 2) if total_votes else 0
 
        items.append(
            {
                "election_id": election_id,
                "title": title,
                "winner": winner_name,
                "votes": winner_votes,
                "total_votes": total_votes,
                "percentage": percentage,
                "result_published_at": published_at,
            }
        )
 
    return {
        "items": items,
        "pagination": {
            "                                                                                                                    page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit,
        },
    }
 
 
# =========================================================
# PUBLIC SERVICE - PUBLISH RESULTS
# =========================================================
 
async def publish_results(db: AsyncSession, data: dict):
    """Publish completed election results"""
 
    elections = (
        await db.execute(
            select(Election).where(
                Election.status == "COMPLETED",
                Election.result_published == False,
            )
        )
    ).scalars().all()
 
    if not elections:
        return {"message": "No completed elections to publish", "count": 0}
 
    count = 0
 
    for e in elections:
        e.result_published = True
        e.result_published_at = datetime.utcnow()
 
        notification = Notification(
            admin_id=e.admin_id,
            election_id=e.election_id,
            assembly_id=None,
            type=NotificationType.RESULT,
            title="Election Result Published",
            message="Election results are now live.",
            recipients_count=0,
            email_sent=False,
        )
 
        db.add(notification)
        count += 1
 
    await db.commit()
 
    return {"message": "Results published", "count": count}
 
 
# =========================================================
# PUBLIC SERVICE - UNPUBLISH RESULTS
# =========================================================
 
async def unpublish_results(db: AsyncSession, data: dict):
    """Unpublish election results"""
 
    elections = (
        await db.execute(select(Election).where(Election.result_published == True))
    ).scalars().all()
 
    if not elections:
        return {"message": "No published elections", "count": 0}
 
    election_ids = [e.election_id for e in elections]
 
    for e in elections:
        e.result_published = False
        e.result_published_at = None
 
    await db.execute(
        delete(Notification).where(
            Notification.election_id.in_(election_ids),
            Notification.type == NotificationType.RESULT,
        )
    )
 
    await db.commit()
 
    return {"message": "Results unpublished", "count": len(elections)}
 
 
# =========================================================
# PUBLIC SERVICE - CALCULATE WINNER
# =========================================================
 
async def calculate_election_winner(db: AsyncSession, election_id: int):
    """Calculate and determine the winner of an election"""
 
    election = await db.get(Election, election_id)
    if not election:
        return {"error": "Election not found"}
 
    vote_counts = (
        await db.execute(
            select(Vote.candidate_id, func.count(Vote.vote_id))
            .where(Vote.election_id == election_id)
            .group_by(Vote.candidate_id)
        )
    ).all()
 
    if not vote_counts:
        return {"error": "No votes found"}
 
    await db.execute(
        update(Candidate)
        .where(Candidate.election_id == election_id)
        .values(vote_count=0, is_winner=False)
    )
 
    max_votes = max(count for _, count in vote_counts)
    winners = []
 
    for candidate_id, count in vote_counts:
        is_winner = count == max_votes
 
        await db.execute(
            update(Candidate)
            .where(Candidate.candidate_id == candidate_id)
            .values(vote_count=count, is_winner=is_winner)
        )
 
        if is_winner:
            winners.append(candidate_id)
 
    election.status = "COMPLETED"
 
    await db.commit()
 
    return {
        "message": "Winner calculated",
        "election_id": election_id,
        "winner_candidate_ids": winners,
        "max_votes": max_votes,
    }
 
 
# =========================================================
# ADMIN SERVICE - GET ALL RESULTS (WITH FILTERS)
# =========================================================
from sqlalchemy import select, func
from collections import defaultdict
 
 
async def admin_get_all_results(db: AsyncSession, admin_id: int, filters: AdminResultsFilterParams):
 
    # =========================================================
    # 1️⃣ MAIN QUERY → WINNER DATA
    # =========================================================
    query = (
        select(
            Election.election_id,
            Election.title,
            Election.election_level,
            Member.name.label("winner_name"),
            Candidate.vote_count.label("winner_votes"),
            Election.total_votes,
            Election.winner_percentage,
            Election.result_published,
            Election.result_published_at,
            Election.created_at,
            State.state_name,
            District.district_name,
            Assembly.assembly_name,
            Mandal.mandal_name,
            Village.village_name,
            Ward.ward_number,
        )
        .join(Candidate, Candidate.election_id == Election.election_id)
        .join(Member, Member.member_id == Candidate.member_id)
        .join(Ward, Ward.ward_id == Election.ward_id)
        .join(Village, Village.village_id == Ward.village_id)
        .join(Mandal, Mandal.mandal_id == Village.mandal_id)
        .join(Assembly, Assembly.assembly_id == Mandal.assembly_id)
        .join(District, District.district_id == Assembly.district_id)
        .join(State, State.state_id == District.state_id)
        .where(
            Election.status == filters.status,
            Election.admin_id == admin_id,
            Candidate.is_winner == True,
        )
        .order_by(Election.created_at.desc())
    )
 
    # Filters
    if filters.state_id:
        query = query.where(State.state_id == filters.state_id)
    if filters.district_id:
        query = query.where(District.district_id == filters.district_id)
    if filters.assembly_id:
        query = query.where(Assembly.assembly_id == filters.assembly_id)
    if filters.election_level:
        query = query.where(Election.election_level == filters.election_level)
 
    # =========================================================
    # 2️⃣ PAGINATION TOTAL
    # =========================================================
    total = (
        await db.execute(
            select(func.count(Election.election_id)).where(
                Election.status == filters.status,
                Election.admin_id == admin_id,
            )
        )
    ).scalar() or 0
 
    rows = (
        await db.execute(
            query.offset((filters.page - 1) * filters.limit).limit(filters.limit)
        )
    ).all()
 
    if not rows:
        return {"items": [], "pagination": {"page": filters.page, "limit": filters.limit, "total": 0, "pages": 0}}
 
    # =========================================================
    # 3️⃣ FETCH ALL CANDIDATES FOR THESE ELECTIONS
    # =========================================================
    election_ids = [row[0] for row in rows]
 
    candidates_query = (
        select(
            Candidate.election_id,
            Member.name,
            Candidate.vote_count,
            Candidate.is_winner,
        )
        .join(Member, Member.member_id == Candidate.member_id)
        .where(Candidate.election_id.in_(election_ids))
        .order_by(Candidate.vote_count.desc())
    )
 
    candidate_rows = (await db.execute(candidates_query)).all()
 
   
    candidates_map = defaultdict(list)
 
    for election_id, name, votes, is_winner in candidate_rows:
        candidates_map[election_id].append(
            {
                "name": name,
                "votes": votes,
                "is_winner": is_winner,
            }
        )
 
    # =========================================================
    # 4 BUILD FINAL RESPONSE
    # =========================================================
    items = []
 
    for row in rows:
        (
            election_id,
            title,
            election_level,
            winner_name,
            winner_votes,
            total_votes,
            winner_percentage,
            result_published,
            result_published_at,
            created_at,
            state_name,
            district_name,
            assembly_name,
            mandal_name,
            village_name,
            ward_number,
        ) = row
 
        items.append(
            {
                "election_id": election_id,
                "title": title,
                "election_level": election_level,
                "winner_name": winner_name,
                "winner_votes": winner_votes,
                "total_votes": total_votes,
                "percentage": winner_percentage,
 
                "state_name": state_name,
                "district_name": district_name,
                "assembly_name": assembly_name,
                "mandal_name": mandal_name,
                "village_name": village_name,
                "ward_number": ward_number,
 
                "result_published": result_published,
                "result_published_at": result_published_at.isoformat() if result_published_at else None,
                "created_at": created_at.isoformat() if created_at else None,
 
                # ⭐ NEW → all candidates list
                "candidates": candidates_map.get(election_id, []),
            }
        )
 
    return {
        "items": items,
        "pagination": {
            "page": filters.page,
            "limit": filters.limit,
            "total": total,
            "pages": (total + filters.limit - 1) // filters.limit,
        },
    }
 
 
 
 
async def admin_publish_election_result(
    db: AsyncSession,
    admin_id: int,
    election_id: int,
):
    """Admin publishes a specific completed election result"""
 
    election = await db.get(Election, election_id)
 
    if not election:
        return {"error": "Election not found", "status": 404}
 
    if election.admin_id != admin_id:
        return {"error": "Unauthorized: You can only publish your own elections", "status": 403}
 
    if election.status != "COMPLETED":
        return {
            "error": f"Election is {election.status}. Only COMPLETED elections can be published.",
            "status": 400,
        }
 
    if election.result_published:
        return {"error": "Election result is already published", "status": 400}
 
    election.result_published = True
    election.result_published_at = datetime.utcnow()
 
    notification = Notification(
        admin_id=election.admin_id,
        election_id=election.election_id,
        assembly_id=None,
        type=NotificationType.RESULT,
        title="Election Result Published",
        message=f"Results for '{election.title}' are now live.",
        recipients_count=0,
        email_sent=False,
    )
 
    db.add(notification)
    await db.commit()
 
    return {
        "message": "Election result published successfully",
        "election_id": election_id,
        "published_at": election.result_published_at.isoformat(),
        "status": 200,
    }
 
 
 
 
async def admin_unpublish_election_result(
    db: AsyncSession,
    admin_id: int,
    election_id: int,
):
    """Admin unpublishes a published election result"""
 
    election = await db.get(Election, election_id)
 
    if not election:
        return {"error": "Election not found", "status": 404}
 
    if election.admin_id != admin_id:
        return {"error": "Unauthorized: You can only unpublish your own elections", "status": 403}
 
    if not election.result_published:
        return {"error": "Election result is not published", "status": 400}
 
    election.result_published = False
    election.result_published_at = None
 
    await db.execute(
        delete(Notification).where(
            Notification.election_id == election_id,
            Notification.type == NotificationType.RESULT,
        )
    )
 
    await db.commit()
 
    return {
        "message": "Election result unpublished successfully",
        "election_id": election_id,
        "status": 200,
    }
 
 
 
 
 
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from collections import defaultdict
from fastapi import HTTPException
 
from app.models.models import (
    Election,
    Candidate,
    Member,
    Ward,
    Village,
    Mandal,
)
 
 
async def get_results_by_scope(
    db: AsyncSession,
    assembly_id: int | None,
    mandal_id: int | None,
    village_id: int | None,
    ward_id: int | None,
    page: int,
    limit: int,
):
 
    # -------------------------------------------------
    # 1️⃣ Base Query (Published + Completed + Winner)
    # -------------------------------------------------
    query = (
        select(
            Election.election_id,
            Election.title,
            Election.ward_id,
            Member.name.label("winner_name"),
            Candidate.vote_count.label("winner_votes"),
            Election.total_votes,
            Election.winner_percentage,
            Election.result_published_at,
        )
        .join(Candidate, Candidate.election_id == Election.election_id)
        .join(Member, Member.member_id == Candidate.member_id)
        .where(
            Election.status == "COMPLETED",
            Election.result_published == True,
            Candidate.is_winner == True,
        )
        .order_by(Election.created_at.desc())
    )
 
    # -------------------------------------------------
    # 2️⃣ Apply Hierarchy Scope Filter
    # -------------------------------------------------
    if ward_id:
        query = query.where(Election.ward_id == ward_id)
 
    elif village_id:
        query = (
            query
            .join(Ward, Ward.ward_id == Election.ward_id)
            .where(Ward.village_id == village_id)
        )
 
    elif mandal_id:
        query = (
            query
            .join(Ward, Ward.ward_id == Election.ward_id)
            .join(Village, Village.village_id == Ward.village_id)
            .where(Village.mandal_id == mandal_id)
        )
 
    elif assembly_id:
        query = (
            query
            .join(Ward, Ward.ward_id == Election.ward_id)
            .join(Village, Village.village_id == Ward.village_id)
            .join(Mandal, Mandal.mandal_id == Village.mandal_id)
            .where(Mandal.assembly_id == assembly_id)
        )
 
    else:
        raise HTTPException(status_code=400, detail="At least one scope ID required")
 
    # -------------------------------------------------
    # 3️⃣ Pagination Count
    # -------------------------------------------------
    total_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_query)).scalar() or 0
 
    rows = (
        await db.execute(
            query.offset((page - 1) * limit).limit(limit)
        )
    ).all()
 
    if not rows:
        return {
            "items": [],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": 0,
                "pages": 0,
            },
        }
 
    # -------------------------------------------------
    # 4️⃣ Fetch All Candidates For These Elections
    # -------------------------------------------------
    election_ids = [row[0] for row in rows]
 
    candidate_query = (
        select(
            Candidate.election_id,
            Member.name,
            Candidate.vote_count,
            Candidate.is_winner,
        )
        .join(Member, Member.member_id == Candidate.member_id)
        .where(Candidate.election_id.in_(election_ids))
        .order_by(Candidate.vote_count.desc())
    )
 
    candidate_rows = (await db.execute(candidate_query)).all()
 
    candidate_map = defaultdict(list)
 
    for election_id, name, votes, is_winner in candidate_rows:
        candidate_map[election_id].append(
            {
                "name": name,
                "votes": votes,
                "is_winner": is_winner,
            }
        )
 
    # -------------------------------------------------
    # 5️⃣ Final Response Format
    # -------------------------------------------------
    items = []
 
    for (
        election_id,
        title,
        ward_id,
        winner_name,
        winner_votes,
        total_votes,
        percentage,
        published_at,
    ) in rows:
 
        items.append({
            "election_id": election_id,
            "title": title,
            "ward_id": ward_id,
            "winner_name": winner_name,
            "winner_votes": winner_votes,
            "total_votes": total_votes,
            "percentage": percentage,
            "result_published_at": published_at,
            "candidates": candidate_map.get(election_id, []),
        })
 
    return {
        "items": items,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit,
        },
    }
 