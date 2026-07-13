import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.machine import MachineStatus, Role


class GeneratePairCodeRequest(BaseModel):
    machine_name: str


class GeneratePairCodeResponse(BaseModel):
    code: str
    expires_in_seconds: int
    
class AgentRegisterRequest(BaseModel):
    machine_name: str | None = None
    hostname: str | None = None
    os: str | None = None


class AgentPairRequest(BaseModel):
    """Sent by the agent binary once the user types the pairing code in it."""
    code: str


class AgentPairResponse(BaseModel):
    machine_uid: str
    secret: str  # returned exactly once — the agent stores this locally and it is never shown again


class MachineOut(BaseModel):
    id: uuid.UUID
    name: str
    machine_uid: str
    status: MachineStatus
    last_seen: datetime | None
    os: str | None
    cpu_percent: float | None
    ram_percent: float | None
    disk_percent: float | None
    ip_address: str | None

    class Config:
        from_attributes = True


class MachineRenameRequest(BaseModel):
    name: str


class MachineAccessGrantRequest(BaseModel):
    user_email: str
    role: Role
