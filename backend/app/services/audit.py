from sqlalchemy.orm import Session

from app.models.command import AuditLog


def log_event(
    db: Session,
    *,
    user_id: str | None,
    action: str,
    resource: str | None = None,
    ip_address: str | None = None,
    result: str = "success",
    detail: dict | None = None,
) -> None:
    """
    Append-only audit trail. Called from every sensitive endpoint (login,
    command dispatch, pairing, role changes, ...) so events can be
    reconstructed later: who did what, when, from where, and whether it
    succeeded.
    """
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        ip_address=ip_address,
        result=result,
        detail=detail,
    )
    db.add(entry)
    db.commit()
