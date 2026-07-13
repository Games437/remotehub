import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.command import CommandStatus, CommandType


class SendCommandRequest(BaseModel):
    command_type: CommandType
    payload: dict | None = None  # e.g. {"url": "https://..."} for open_website


class CommandOut(BaseModel):
    id: uuid.UUID
    machine_id: uuid.UUID
    command_type: CommandType
    status: CommandStatus
    result: dict | None
    created_at: datetime

    class Config:
        from_attributes = True


class AgentCommandAck(BaseModel):
    """The agent posts this back over the websocket once a command finishes."""
    command_id: uuid.UUID
    success: bool
    result: dict | None = None
