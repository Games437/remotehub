import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class CommandType(str, enum.Enum):
    open_website = "open_website"
    open_program = "open_program"
    play_music = "play_music"
    shutdown = "shutdown"
    restart = "restart"
    cancel_shutdown = "cancel_shutdown"
    sleep = "sleep"
    lock = "lock"
    screenshot = "screenshot"
    notification = "notification"
    clipboard = "clipboard"
    get_idle_time = "get_idle_time"
    list_processes = "list_processes"
    get_active_window = "get_active_window"
    list_open_windows = "list_open_windows"
    get_network_status = "get_network_status"
    get_system_info = "get_system_info"
    kill_process = "kill_process"
    send_message = "send_message"
    health_check = "health_check"
    list_folder = "list_folder"
    fetch_file = "fetch_file"


class CommandStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    acknowledged = "acknowledged"
    failed = "failed"


class Command(Base):
    __tablename__ = "commands"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    machine_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "machines.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    issued_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    command_type: Mapped[CommandType] = mapped_column(Enum(CommandType), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[int] = mapped_column(Integer, nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[CommandStatus] = mapped_column(Enum(CommandStatus), nullable=False, default=CommandStatus.pending)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    machine = relationship(
        "Machine",
        back_populates="commands",
    )


class ChatMessage(Base):
    """Two-way chat between an admin (via dashboard) and a machine's agent.
    Admin messages are pushed live over the websocket in addition to being
    stored here; agent replies arrive via a separate machine-authenticated
    HTTP endpoint (the agent's GUI runs on its own thread, independent of
    the asyncio websocket loop — an HTTP POST is simpler and more robust
    than bridging the two)."""
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"), nullable=False)
    sender: Mapped[str] = mapped_column(String(10))  # "admin" | "agent"
    message: Mapped[str] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AuditLog(Base):
    """Layer 7 — Audit log. Append-only; never update or delete rows."""
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    resource: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[str] = mapped_column(String(20))  # success | failure
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
