import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_machine_or_404, require_role
from app.core.config import settings
from app.core.security import generate_agent_secret, generate_pair_code
from app.db.database import get_db
from app.models.machine import Machine, MachineAccess, MachineStatus, PairingCode, Role
from app.models.user import User
from app.schemas.machine import (
    AgentPairRequest,
    AgentPairResponse,
    GeneratePairCodeRequest,
    GeneratePairCodeResponse,
    MachineAccessGrantRequest,
    MachineOut,
    MachineRenameRequest,
)
from app.services.audit import log_event
from app.websocket.manager import manager

from app.schemas.machine import AgentRegisterRequest

router = APIRouter(prefix="/machines", tags=["machines"])


@router.get("", response_model=list[MachineOut])
def list_machines(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned = db.query(Machine).filter(Machine.owner_id == user.id)
    shared_ids = [g.machine_id for g in db.query(MachineAccess).filter(MachineAccess.user_id == user.id)]
    shared = db.query(Machine).filter(Machine.id.in_(shared_ids)) if shared_ids else []
    machines = list(owned) + list(shared)

    # The `status` column only flips back to offline on a *clean* websocket
    # disconnect (see agent_ws.py's `finally` block). If this backend
    # process was ever killed abruptly (container restart, crash) while an
    # agent was connected, that cleanup never ran and the row is stuck on
    # "online" forever — even though this process's live connection table
    # (`manager`) has no such connection at all. `manager.is_online()`
    # reflects what's actually connected right now, so it's the source of
    # truth for display; reconcile any mismatch (and persist the fix so
    # direct DB reads elsewhere see it too).
    dirty = False
    for machine in machines:
        live = manager.is_online(machine.id)
        if machine.status == MachineStatus.online and not live:
            machine.status = MachineStatus.offline
            machine.cpu_percent = 0.0
            machine.ram_percent = 0.0
            machine.disk_percent = 0.0
            dirty = True
    if dirty:
        db.commit()

    return machines


@router.post("/pair/generate-code", response_model=GeneratePairCodeResponse)
def generate_pairing_code(
    body: GeneratePairCodeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Layer 4 — Step 1. The logged-in website generates a short-lived,
    human-typeable code. The person installing the agent enters this code
    on the machine itself, which is what actually binds that machine to
    this account (the code alone, without agent-side entry, grants nothing).
    """
    code = generate_pair_code()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.PAIR_CODE_TTL_SECONDS)
    db.add(PairingCode(code=code, user_id=user.id, machine_name=body.machine_name, expires_at=expires_at))
    db.commit()
    return GeneratePairCodeResponse(code=code, expires_in_seconds=settings.PAIR_CODE_TTL_SECONDS)


@router.post("/pair/redeem", response_model=AgentPairResponse)
def redeem_pairing_code(body: AgentPairRequest, db: Session = Depends(get_db)):
    """
    Layer 4 — Step 2. Called by the agent binary (not the browser) once the
    installer types the code in. Returns the permanent per-machine secret;
    this is the only time it is ever sent, so the agent must persist it
    locally (e.g. in an OS-protected credential store).
    """
    pairing = (
        db.query(PairingCode)
        .filter(PairingCode.code == body.code.upper(), PairingCode.used.is_(False))
        .first()
    )
    if not pairing or pairing.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired pairing code")

    machine = Machine(
        owner_id=pairing.user_id,
        name=pairing.machine_name,
        machine_uid=secrets.token_hex(16),
        secret=generate_agent_secret(),
        paired=True,
    )
    db.add(machine)
    pairing.used = True
    db.commit()
    db.refresh(machine)

    log_event(db, user_id=str(pairing.user_id), action="machine_paired", resource=str(machine.id))
    return AgentPairResponse(machine_uid=machine.machine_uid, secret=machine.secret)

@router.post("/register", response_model=AgentPairResponse, status_code=status.HTTP_201_CREATED)
def register_machine_direct(
    body: AgentRegisterRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Direct agent registration — the agent authenticates as the user
    (email/password login) and registers itself in one step, without a
    human needing to generate/type a pairing code first. Used by the
    normal "Login" flow in the agent GUI. The pairing-code flow above
    remains for machines where entering the account password isn't
    appropriate (shared/customer machines).
    """
    machine = Machine(
        owner_id=user.id,
        name=body.machine_name or body.hostname or "Unnamed machine",
        machine_uid=secrets.token_hex(16),
        secret=generate_agent_secret(),
        paired=True,
    )
    db.add(machine)
    db.commit()
    db.refresh(machine)

    log_event(db, user_id=str(user.id), action="machine_registered_direct", resource=str(machine.id))
    return AgentPairResponse(machine_uid=machine.machine_uid, secret=machine.secret)

@router.patch("/{machine_id}", response_model=MachineOut)
def rename_machine(
    machine_id: uuid.UUID,
    body: MachineRenameRequest,
    machine: Machine = Depends(require_role(Role.admin)),
    db: Session = Depends(get_db),
):
    machine.name = body.name
    db.commit()
    db.refresh(machine)
    return machine


@router.delete("/{machine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_machine(
    machine_id: uuid.UUID,
    user: User = Depends(get_current_user),
    machine: Machine = Depends(get_machine_or_404),
    db: Session = Depends(get_db),
):
    if machine.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete a machine")
    db.delete(machine)
    db.commit()
    log_event(db, user_id=str(user.id), action="machine_deleted", resource=str(machine_id))


@router.post("/{machine_id}/access", status_code=status.HTTP_204_NO_CONTENT)
def grant_access(
    machine_id: uuid.UUID,
    body: MachineAccessGrantRequest,
    user: User = Depends(get_current_user),
    machine: Machine = Depends(get_machine_or_404),
    db: Session = Depends(get_db),
):
    """Layer 6 — Only the owner can grant/change roles on their machine."""
    if machine.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can manage access")

    target = db.query(User).filter(User.email == body.user_email).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    grant = (
        db.query(MachineAccess)
        .filter(MachineAccess.machine_id == machine.id, MachineAccess.user_id == target.id)
        .first()
    )
    if grant:
        grant.role = body.role
    else:
        db.add(MachineAccess(machine_id=machine.id, user_id=target.id, role=body.role))
    db.commit()
    log_event(
        db, user_id=str(user.id), action="access_granted", resource=str(machine.id),
        detail={"target_user": body.user_email, "role": body.role.value},
    )
