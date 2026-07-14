import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.command import AuditLog
from app.models.user import User

router = APIRouter(prefix="/audit-logs", tags=["audit"])


class AuditLogOut(BaseModel):
    id: uuid.UUID
    action: str
    resource: str | None
    ip_address: str | None
    result: str
    detail: dict | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=list[AuditLogOut])
def list_my_audit_logs(
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the current user's own activity — logins, commands they issued,
    pairing, role changes, etc. — newest first. This is the substitute for
    "seeing what happened" when there's no live screen to watch: every
    action that was taken is reconstructable here after the fact.
    """
    return (
        db.query(AuditLog)
        .filter(AuditLog.user_id == user.id)
        .order_by(AuditLog.created_at.desc())
        .limit(min(limit, 500))
        .all()
    )
