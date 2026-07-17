import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SendChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatReplyRequest(BaseModel):
    """Submitted by the agent directly (not through the websocket) — see
    core/security.verify_chat_reply for how this is authenticated without
    a user JWT, since the agent isn't a logged-in user."""
    machine_uid: str
    message: str = Field(min_length=1, max_length=2000)
    timestamp: int
    nonce: str
    signature: str


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    sender: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True
