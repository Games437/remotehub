"""
Agent <-> server live channel.

Handshake (Layer 3):
  1. Agent opens the websocket and sends {"machine_uid": "..."}
  2. Server looks up the machine, generates a random nonce, sends it back
  3. Agent HMAC-signs the nonce with its stored secret and replies
     {"signature": "..."}
  4. Server verifies the signature server-side (never re-derives or trusts
     a client-sent secret) and only then marks the machine online.

After the handshake the socket carries two message types:
  - server -> agent : {"type": "command", "command_id", "command_type",
                        "payload", "timestamp", "nonce", "signature"}
  - agent -> server  : {"type": "status", "cpu", "ram", "disk", "os", "ip"}
                       {"type": "ack", "command_id", "success", "result"}
"""
import json
import secrets
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.security import verify_agent_challenge
from app.db.database import SessionLocal
from app.models.command import Command, CommandStatus
from app.models.machine import Machine, MachineStatus
from app.websocket.manager import manager

router = APIRouter()


async def _handshake(ws: WebSocket, db: Session) -> Machine | None:
    hello_raw = await ws.receive_text()
    hello = json.loads(hello_raw)
    machine = db.query(Machine).filter(Machine.machine_uid == hello.get("machine_uid")).first()
    if machine is None or not machine.paired:
        await ws.close(code=4001, reason="unknown machine")
        return None

    nonce = secrets.token_hex(16)
    await ws.send_text(json.dumps({"type": "challenge", "nonce": nonce}))

    reply_raw = await ws.receive_text()
    reply = json.loads(reply_raw)
    ok = verify_agent_challenge(machine.machine_uid, machine.secret, nonce, reply.get("signature", ""))
    if not ok:
        await ws.close(code=4003, reason="bad signature")
        return None

    return machine


@router.websocket("/ws/agent")
async def agent_socket(ws: WebSocket):
    await ws.accept()
    db = SessionLocal()
    machine: Machine | None = None
    try:
        machine = await _handshake(ws, db)
        if machine is None:
            return

        machine.status = MachineStatus.online
        machine.last_seen = datetime.now(timezone.utc)
        db.commit()
        await manager.connect(machine.id, ws)

        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "status":
                machine.cpu_percent = msg.get("cpu")
                machine.ram_percent = msg.get("ram")
                machine.disk_percent = msg.get("disk")
                machine.os = msg.get("os") or machine.os
                machine.ip_address = msg.get("ip") or machine.ip_address
                machine.last_seen = datetime.now(timezone.utc)
                db.commit()

            elif msg_type == "ack":
                cmd = db.get(Command, uuid.UUID(msg["command_id"]))
                if cmd is not None:
                    cmd.status = CommandStatus.acknowledged if msg.get("success") else CommandStatus.failed
                    cmd.result = msg.get("result")
                    db.commit()

    except WebSocketDisconnect:
        pass
    finally:
        if machine is not None:
            manager.disconnect(machine.id)
            machine.status = MachineStatus.offline
            machine.last_seen = datetime.now(timezone.utc)
            db.commit()
        db.close()