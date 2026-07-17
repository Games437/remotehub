import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import enforce_rate_limit, get_current_user, require_role
from app.core.security import verify_chat_reply
from app.db.database import get_db
from app.models.command import ChatMessage
from app.models.machine import Machine, Role
from app.models.user import User
from app.schemas.chat import ChatMessageOut, ChatReplyRequest, SendChatRequest
from app.websocket.manager import manager

router = APIRouter(prefix="/machines/{machine_id}/chat", tags=["chat"])

# The agent replies over plain HTTP (not the websocket — its GUI runs on a
# separate thread from the asyncio loop, and bridging the two just to send
# a chat reply isn't worth the complexity). It doesn't know the machine's
# internal id, only its own machine_uid, so this lives on its own path
# rather than nested under /machines/{machine_id}/.
agent_router = APIRouter(prefix="/agent/chat", tags=["chat"])


@router.get("", response_model=list[ChatMessageOut])
def list_chat(
    machine_id: uuid.UUID,
    machine: Machine = Depends(require_role(Role.viewer)),
    db: Session = Depends(get_db),
):
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.machine_id == machine.id)
        .order_by(ChatMessage.created_at.asc())
        .limit(200)
        .all()
    )


@router.post("", response_model=ChatMessageOut, status_code=status.HTTP_201_CREATED)
async def send_chat(
    machine_id: uuid.UUID,
    body: SendChatRequest,
    user: User = Depends(get_current_user),
    machine: Machine = Depends(require_role(Role.member)),
    db: Session = Depends(get_db),
    _: None = Depends(enforce_rate_limit),
):
    entry = ChatMessage(machine_id=machine.id, sender="admin", message=body.message)
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # Best-effort live push. If the agent isn't connected right now it
    # just won't see this until it's back online and someone reopens the
    # chat panel to look at history — there's no offline queue for chat.
    await manager.send_command(machine.id, {"type": "chat", "message": body.message})

    return entry


@agent_router.post("/reply", response_model=ChatMessageOut, status_code=status.HTTP_201_CREATED)
def reply_chat(body: ChatReplyRequest, db: Session = Depends(get_db)):
    machine = db.query(Machine).filter(Machine.machine_uid == body.machine_uid).first()
    if machine is None or not machine.paired:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown machine")

    ok, reason = verify_chat_reply(machine.secret, body.message, body.timestamp, body.nonce, body.signature)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=reason)

    entry = ChatMessage(machine_id=machine.id, sender="agent", message=body.message)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
