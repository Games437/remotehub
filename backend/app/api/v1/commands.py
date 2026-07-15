import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import enforce_rate_limit, get_current_user, require_role
from app.core.security import generate_nonce, sign_command
from app.db.database import get_db
from app.models.command import Command, CommandStatus
from app.models.machine import Machine, Role
from app.models.user import User
from app.schemas.command import CommandOut, SendCommandRequest
from app.services.audit import log_event
from app.websocket.manager import manager
from datetime import datetime, timezone
from fastapi import status

router = APIRouter(prefix="/machines/{machine_id}/commands", tags=["commands"])

# Viewers can look, but only member+ can act on a machine.
_ACTION_MIN_ROLE = Role.member


@router.get("", response_model=list[CommandOut])
def list_commands(
    machine_id: uuid.UUID,
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    machine: Machine = Depends(require_role(Role.viewer)),
    db: Session = Depends(get_db),
):
    base_query = db.query(Command).filter(Command.machine_id == machine.id)
    # Total count of *all* commands for this machine, not just this page —
    # the frontend needs this to render "page X of Y" / disable Next.
    response.headers["X-Total-Count"] = str(base_query.count())
    return (
        base_query
        .order_by(Command.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post("", response_model=CommandOut, dependencies=[Depends(enforce_rate_limit)])
async def send_command(
    machine_id: uuid.UUID,
    body: SendCommandRequest,
    request: Request,
    user: User = Depends(get_current_user),
    machine: Machine = Depends(require_role(_ACTION_MIN_ROLE)),
    db: Session = Depends(get_db),
):
    if not manager.is_online(machine.id):
        raise HTTPException(status_code=409, detail="Machine is offline")

    timestamp = int(time.time())
    nonce = generate_nonce()
    # Layer 5 — sign with the machine's own secret so the agent can verify
    # the command actually came from our server and hasn't been replayed.
    signature = sign_command(machine.secret, body.command_type.value, timestamp, nonce)

    command = Command(
        machine_id=machine.id,
        issued_by=user.id,
        command_type=body.command_type,
        payload=body.payload,
        timestamp=timestamp,
        nonce=nonce,
        signature=signature,
        status=CommandStatus.pending,
    )
    db.add(command)
    db.commit()
    db.refresh(command)

    delivered = await manager.send_command(
        machine.id,
        {
            "type": "command",
            "command_id": str(command.id),
            "command_type": body.command_type.value,
            "payload": body.payload,
            "timestamp": timestamp,
            "nonce": nonce,
            "signature": signature,
        },
    )
    command.status = CommandStatus.sent if delivered else CommandStatus.failed
    db.commit()
    db.refresh(command)

    log_event(
        db, user_id=str(user.id), action="command_sent", resource=str(machine.id),
        ip_address=request.client.host if request.client else None,
        detail={"command_type": body.command_type.value, "command_id": str(command.id)},
    )
    return command

@router.delete("/{command_id}/result", status_code=status.HTTP_204_NO_CONTENT)
def purge_command_result(
    machine_id: uuid.UUID,
    command_id: uuid.UUID,
    user: User = Depends(get_current_user),
    machine: Machine = Depends(require_role(Role.viewer)),
    db: Session = Depends(get_db),
):
    command = db.query(Command).filter(Command.id == command_id, Command.machine_id == machine.id).first()
    if command is None:
        raise HTTPException(status_code=404, detail="Command not found")

    if isinstance(command.result, dict):
        remaining = {k: v for k, v in command.result.items() if k != "image_base64"}
        remaining["purged_at"] = datetime.now(timezone.utc).isoformat()
        command.result = remaining
        db.commit()

    log_event(db, user_id=str(user.id), action="command_result_purged", resource=str(command.id))