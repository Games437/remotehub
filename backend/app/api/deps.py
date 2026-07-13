import uuid

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.rate_limit import rate_limit
from app.core.security import decode_token
from app.db.database import get_db
from app.models.machine import Machine, MachineAccess, Role
from app.models.user import User

bearer_scheme = HTTPBearer()

_ROLE_RANK = {Role.viewer: 0, Role.member: 1, Role.admin: 2, Role.owner: 3}


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = creds.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise ValueError("wrong token type")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or disabled")
    return user


async def enforce_rate_limit(request: Request, user: User = Depends(get_current_user)) -> None:
    await rate_limit(request, user_id=str(user.id))


def get_machine_or_404(machine_id: uuid.UUID, db: Session = Depends(get_db)) -> Machine:
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found")
    return machine


def require_role(minimum: Role):
    """
    Layer 6 — Role based access. Returns a FastAPI dependency that 403s
    unless the current user is the machine owner or holds a role >= `minimum`.
    """

    def _checker(
        machine: Machine = Depends(get_machine_or_404),
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Machine:
        if machine.owner_id == user.id:
            return machine

        grant = (
            db.query(MachineAccess)
            .filter(MachineAccess.machine_id == machine.id, MachineAccess.user_id == user.id)
            .first()
        )
        if grant is None or _ROLE_RANK[grant.role] < _ROLE_RANK[minimum]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role for this action")
        return machine

    return _checker
