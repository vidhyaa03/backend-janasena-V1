from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import pytz
import asyncio

from app.models.models import (
    ElectionEvent, Election,
    Ward, Village, Mandal, Assembly,
    Member, Notification, NotificationType
)
from app.core.email import send_email

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.models.models import Nomination, Candidate
IST = pytz.timezone("Asia/Kolkata")



async def create_nomination_notification(
    db: AsyncSession,
    event_id: int,
    admin_id: int,
):
    """
    Send professional Telugu nomination notification
    personalized with member name & ward.
    """

    # 1️⃣ Get event
    event = await db.get(ElectionEvent, event_id)
    if not event:
        raise ValueError("Election event not found")

    assembly_id = event.assembly_id

    # 2️⃣ Get eligible members with ward name
    result = await db.execute(
        select(Member, Ward.ward_name)
        .join(Ward, Ward.ward_id == Member.ward_id)
        .join(Village, Village.village_id == Ward.village_id)
        .join(Mandal, Mandal.mandal_id == Village.mandal_id)
        .where(
            Mandal.assembly_id == assembly_id,
            Member.is_active.is_(True),
            Member.is_eligible_to_vote.is_(True),
        )
    )

    rows = result.all()
    recipients_count = len(rows)

    # 3️⃣ Format dates in readable IST
    def fmt(dt):
        if not dt:
            return "-"
        return dt.astimezone(IST).strftime("%d %B %Y, %I:%M %p")

    # 4️⃣ Save notification (template message only)
    notification = Notification(
        admin_id=admin_id,
        assembly_id=assembly_id,
        type=NotificationType.NOMINATION,
        title=f"నామినేషన్లు ప్రారంభం – {event.title}",
        message="Nomination notification sent",
        recipients_count=recipients_count,
    )

    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    # 5️⃣ Safe email sender
    async def safe_send(email, subject, body):
        try:
            await send_email(email, subject, body)
            return True
        except Exception:
            return False

    # 6️⃣ Prepare & send personalized emails
    tasks = []

    for member, ward_name in rows:

        subject = f"నామినేషన్లు ప్రారంభం – {event.title}"

        body = f"""
ప్రియమైన శ్రీ/శ్రీమతి {member.name} గారికి,

మీరు {ward_name} వార్డు సభ్యుడిగా నమోదయ్యారు.

"{event.title}" ఎన్నికలకు సంబంధించిన నామినేషన్లు అధికారికంగా ప్రారంభమయ్యాయి.

📅 నామినేషన్ ప్రారంభ తేదీ: {fmt(event.nomination_start)}
📅 నామినేషన్ చివరి తేదీ: {fmt(event.nomination_end)}

మీరు అభ్యర్థిగా పోటీ చేయాలని ఆసక్తి ఉంటే,
దయచేసి పై తేదీలలోపు మీ నామినేషన్‌ను సమర్పించండి.

ఈ సమాచారం మీకు సులభంగా అర్థమయ్యే విధంగా పంపించబడింది.
ఏమైనా సందేహాలు ఉంటే స్థానిక ఎన్నికల నిర్వాహకులను సంప్రదించండి.

ధన్యవాదాలు,
ఎన్నికల నిర్వహణ బృందం
"""

        tasks.append(safe_send(member.email, subject, body))

    results = await asyncio.gather(*tasks)
    success_count = sum(results)

    # 7️⃣ Mark email sent
    notification.email_sent = True
    notification.email_sent_at = datetime.now(IST).replace(tzinfo=None)

    await db.commit()

    # 8️⃣ Response
    return {
        "message": "నామినేషన్ నోటిఫికేషన్ విజయవంతంగా పంపబడింది",
        "total_recipients": recipients_count,
        "emails_sent_successfully": success_count,
        "event_id": event_id,
        "notification_id": notification.notification_id,
    }


from sqlalchemy import select, func

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import joinedload
 
from app.models.models import Nomination, Member, Election, Ward, Village, Mandal, Assembly, District
 
 
async def get_all_nominations(db: AsyncSession):
    # -------------------------------
    # Total count
    # -------------------------------
    total_result = await db.execute(select(func.count(Nomination.nomination_id)))
    total = total_result.scalar_one()
    # -------------------------------
    # Fetch nominations with FULL hierarchy
    # -------------------------------
    result = await db.execute(
        select(Nomination)

        .options(

            joinedload(Nomination.member)

                .joinedload(Member.ward)

                .joinedload(Ward.village)

                .joinedload(Village.mandal)

                .joinedload(Mandal.assembly)

                .joinedload(Assembly.district),
 
            joinedload(Nomination.election),
        )

        .order_by(Nomination.applied_at.desc())

    )
    nominations = result.scalars().all()
 
    # -------------------------------

    # Response formatting

    # -------------------------------

    response_items = []
 
    for n in nominations:
 
        # ⭐ Build location string safely

        location = None

        if n.member and n.member.ward:

            ward = n.member.ward

            village = ward.village

            mandal = village.mandal if village else None

            assembly = mandal.assembly if mandal else None

            district = assembly.district if assembly else None
 
            parts = [

                f"Ward {ward.ward_number}" if ward else None,

                village.village_name if village else None,

                mandal.mandal_name if mandal else None,

                assembly.assembly_name if assembly else None,

                district.district_name if district else None,

            ]
 
            location = ", ".join([p for p in parts if p])
 
        response_items.append(

            {

                "nomination_id": n.nomination_id,

                "candidate_id": n.candidate_id,
 
                # Member

                "member_name": n.member.name if n.member else None,

                "member_id": n.member_id,

                "mobile": n.member.mobile if n.member else None,

                "photo_url": n.member.photo_url if n.member else None,
 
                # ⭐ NEW combined hierarchy location

                "location": location,
 
                # Nomination

                "profile_photo_url": n.profile_photo_url,

                "bio": n.bio,

                "status": n.status,

                "applied_at": n.applied_at,

                "reviewed_at": n.reviewed_at,

                "reviewed_by": n.reviewed_by,

                "rejection_reason": n.rejection_reason,

                "approval_notes": n.approval_notes,
 
                # Election

                "election": {

                    "election_id": n.election.election_id,

                    "title": n.election.title,

                    "status": n.election.status,

                } if n.election else None,

            }

        )
 
    return {

        "total": total,

        "nominations": response_items,

    }
 
# ==============================
# Approve nomination
# ==============================
from sqlalchemy import select

from datetime import datetime, timezone
 
async def approve_nomination(db: AsyncSession, nomination_id: int, admin_id: int):

    # Get nomination

    result = await db.execute(

        select(Nomination).where(Nomination.nomination_id == nomination_id)

    )

    nomination = result.scalar_one_or_none()
 
    if not nomination:

        return {"error": "Nomination not found"}
 
    if nomination.status != "PENDING":

        return {"error": "Already reviewed"}
 
    # 🚨 CHECK: member already approved for same election

    existing_candidate = await db.execute(

        select(Candidate).where(
            Candidate.election_id == nomination.election_id,
            Candidate.member_id == nomination.member_id,
        )

    )

    if existing_candidate.scalar_one_or_none():

        return {"error": "Member already has an approved nomination for this election"}
 
    # Create candidate

    candidate = Candidate(

        election_id=nomination.election_id,

        member_id=nomination.member_id,

        status="APPROVED",

    )
 
    db.add(candidate)

    await db.flush()
 
    # Update nomination

    nomination.status = "APPROVED"

    nomination.candidate_id = candidate.candidate_id

    nomination.reviewed_by = admin_id

    nomination.reviewed_at = datetime.now(timezone.utc)
 
    await db.commit()
 
    return {

        "message": "Nomination approved",

        "candidate_id": candidate.candidate_id,

    }
 

# ==============================
# Reject nomination
# ==============================
async def reject_nomination(
    db: AsyncSession,
    nomination_id: int,
    admin_id: int,
    reason: str,
):
    result = await db.execute(
        select(Nomination).where(Nomination.nomination_id == nomination_id)
    )
    nomination = result.scalar_one_or_none()

    if not nomination:
        return {"error": "Nomination not found"}

    if nomination.status != "PENDING":
        return {"error": "Already reviewed"}

    nomination.status = "REJECTED"
    nomination.rejection_reason = reason
    nomination.reviewed_by = admin_id
    nomination.reviewed_at = datetime.now(timezone.utc)

    await db.commit()

    return {"message": "Nomination rejected"}


 
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from fastapi import HTTPException
from collections import defaultdict
 
from app.models.models import (
    Nomination,
    Member,
    Ward,
    Village,
    Mandal,
    Assembly,
)
 
async def get_nominations_by_scope(
    db: AsyncSession,
    assembly_id: int | None,
    mandal_id: int | None,
    village_id: int | None,
    ward_id: int | None,
):
 
    # -------------------------------------------------
    # 1️⃣ Base Query
    # -------------------------------------------------
    query = (
        select(Nomination)
        .join(Member)
        .join(Ward)
        .join(Village)
        .join(Mandal)
        .join(Assembly)
        .options(
            joinedload(Nomination.member)
                .joinedload(Member.ward)
                .joinedload(Ward.village)
                .joinedload(Village.mandal)
                .joinedload(Mandal.assembly),
            joinedload(Nomination.election),
        )
        .order_by(Nomination.applied_at.desc())
    )
 
    # -------------------------------------------------
    # 2️⃣ Scope Filter (Priority Based)
    # -------------------------------------------------
    if ward_id:
        query = query.where(Ward.ward_id == ward_id)
 
    elif village_id:
        query = query.where(Village.village_id == village_id)
 
    elif mandal_id:
        query = query.where(Mandal.mandal_id == mandal_id)
 
    elif assembly_id:
        query = query.where(Assembly.assembly_id == assembly_id)
 
    
    # -------------------------------------------------
    # 3️⃣ Execute Query (No Pagination)
    # -------------------------------------------------
    result = await db.execute(query)
    rows = result.scalars().all()
 
    # -------------------------------------------------
    # 4️⃣ Format Response
    # -------------------------------------------------
    items = []
 
    for n in rows:
 
        ward = n.member.ward if n.member else None
        village = ward.village if ward else None
        mandal = village.mandal if village else None
        assembly = mandal.assembly if mandal else None
 
        location_parts = [
            f"Ward {ward.ward_number}" if ward else None,
            village.village_name if village else None,
            mandal.mandal_name if mandal else None,
            assembly.assembly_name if assembly else None,
        ]
 
        location = ", ".join([p for p in location_parts if p])
 
        items.append({
            "nomination_id": n.nomination_id,
            "candidate_id": n.candidate_id,
            "member_id": n.member_id,
            "member_name": n.member.name if n.member else None,
            "mobile": n.member.mobile if n.member else None,
            "photo_url": n.member.photo_url if n.member else None,
            "location": location,
            "status": n.status,
            "applied_at": n.applied_at,
            "reviewed_at": n.reviewed_at,
            "rejection_reason": n.rejection_reason,
            "election": {
                "election_id": n.election.election_id,
                "title": n.election.title,
                "status": n.election.status,
            } if n.election else None,
        })
 
    return {
        "items": items
    }