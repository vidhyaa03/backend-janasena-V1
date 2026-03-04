from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload




from app.models.models import (
    Notification, NotificationType,
    Assembly, Mandal, Village, Ward, Member
)

from app.core.email import send_email
from datetime import datetime
# =========================================================
# GET ALL NOTIFICATIONS WITH PAGINATION
# =========================================================
async def get_notifications(
    db: AsyncSession,
    page: int = 1,
    limit: int = 20,
):
    page = max(page, 1)
    limit = max(min(limit, 100), 1)

    total = (
        await db.execute(
            select(func.count(Notification.notification_id))
        )
    ).scalar() or 0

    query = (
        select(Notification)
        .options(joinedload(Notification.admin))
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )

    result = await db.execute(query)
    notifications = result.scalars().all()

    items = [
        {
            "id": n.notification_id,
            "title": n.title,
            "message": n.message,
            "recipients_count": n.recipients_count,
            "sent_at": n.created_at,
            "sender_name": n.admin.name if n.admin else "System",
        }
        for n in notifications
    ]

    return {
        "items": items,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit,
        },
    }







async def create_notification_for_assembly(
    db: AsyncSession,
    *,
    admin_id: int,
    assembly_id: int,
    type: NotificationType,
    title: str,
    message: str,
):
    """
    Creates notification for ALL members in an assembly
    and sends email to each member.
    """

   
    assembly = await db.get(Assembly, assembly_id)
    if not assembly:
        return {"message": "Assembly not found"}

   
    member_query = (
        select(Member, Ward, Village, Mandal)
        .join(Ward, Member.ward_id == Ward.ward_id)
        .join(Village, Ward.village_id == Village.village_id)
        .join(Mandal, Village.mandal_id == Mandal.mandal_id)
        .where(Mandal.assembly_id == assembly_id)
    )

    rows = (await db.execute(member_query)).all()

    if not rows:
        return {"message": "No members found in this assembly"}

   
    notification = Notification(
        admin_id=admin_id,
        assembly_id=assembly_id,
        type=type,
        title=title,
        message=message,
        recipients_count=len(rows),
        email_sent=False,
    )

    db.add(notification)
    await db.flush()  # get notification_id

   
    success_count = 0

    for member, ward, village, mandal in rows:
        email_body = f"""
Dear {member.name},

{message}

📍 Location Details
Assembly : {assembly.assembly_name}
Mandal   : {mandal.mandal_name}
Village  : {village.village_name}
Ward     : {ward.ward_name}

This is an automated notification.
Please do not reply.

Regards,
Election Administration
"""

        try:
            await send_email(
                to_email=member.email,
                subject=title,
                body=email_body,
            )
            success_count += 1
        except Exception:
            # continue even if one email fails
            continue

    # --------------------------------------------------
    # 5️⃣ Update email status
    # --------------------------------------------------
    notification.email_sent = success_count > 0
    notification.email_sent_at = datetime.utcnow() if success_count > 0 else None

    await db.commit()

    return {
        "message": "Notification created and emails processed",
        "recipients": len(rows),
        "emails_sent": success_count,
        "notification_id": notification.notification_id,
    }
    
    
    
    
