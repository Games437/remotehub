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

IMPORTANT — how the DB is used here, and why:
This handler is `async def`, but SQLAlchemy's Session here is the plain
synchronous kind. FastAPI auto-threadpools ordinary sync HTTP route
functions for exactly this reason, but that doesn't extend to websocket
handlers — a blocking call made directly here would stall the *entire*
event loop for every connection this process is handling.

The first fix attempt wrapped individual db.query()/db.commit() calls in
run_in_threadpool while reusing one Session object across all of them.
That's not safe: run_in_threadpool doesn't guarantee the same worker
thread runs each call, so the same Session (and the one DBAPI connection
it holds once first used) can end up touched from a different OS thread
on each call. Most DBAPI drivers — especially over SSL, which a hosted
Postgres like Render's requires — aren't safe for that, and the failure
mode isn't a clean exception, it's a silent hang: no error, no close
frame, just nothing, which is exactly what showed up here.

The fix: every DB operation below is a small, self-contained sync
function that opens its own Session, does its work, and closes it, all
within a single run_in_threadpool call (so it only ever touches one
thread, start to finish). Nothing here shares a live Session or
connection across separate awaits.
"""
import json
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.core.security import verify_agent_challenge
from app.db.database import SessionLocal
from app.models.command import Command, CommandStatus
from app.models.machine import Machine, MachineStatus
from app.websocket.manager import manager

router = APIRouter()


# --- Self-contained DB operations — each opens+closes its own Session,
# entirely within one thread. Return plain dicts/values, never live ORM
# objects, so nothing downstream can accidentally touch a Session or
# connection from a different thread than the one that created it. -----

def _fetch_machine(machine_uid: str) -> dict | None:
    with SessionLocal() as db:
        machine = db.query(Machine).filter(Machine.machine_uid == machine_uid).first()
        if machine is None:
            return None
        return {
            "id": machine.id,
            "machine_uid": machine.machine_uid,
            "secret": machine.secret,
            "paired": machine.paired,
        }


def _mark_online(machine_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        machine = db.get(Machine, machine_id)
        if machine is not None:
            machine.status = MachineStatus.online
            machine.last_seen = datetime.now(timezone.utc)
            db.commit()


def _update_status(machine_id: uuid.UUID, cpu, ram, disk, os_name, ip, idle_seconds) -> None:
    with SessionLocal() as db:
        machine = db.get(Machine, machine_id)
        if machine is not None:
            machine.cpu_percent = cpu
            machine.ram_percent = ram
            machine.disk_percent = disk
            machine.os = os_name or machine.os
            machine.ip_address = ip or machine.ip_address
            machine.idle_seconds = idle_seconds
            machine.last_seen = datetime.now(timezone.utc)
            db.commit()


def _update_ack(command_id: uuid.UUID, success: bool, result) -> None:
    with SessionLocal() as db:
        cmd = db.get(Command, command_id)
        if cmd is not None:
            cmd.status = CommandStatus.acknowledged if success else CommandStatus.failed
            cmd.result = result
            db.commit()


def _mark_offline(machine_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        machine = db.get(Machine, machine_id)
        if machine is not None:
            machine.status = MachineStatus.offline
            machine.last_seen = datetime.now(timezone.utc)
            # Stats reflect a live agent reporting in — once it's gone,
            # the old numbers are stale and misleading (e.g. "42% CPU"
            # frozen from 20 minutes ago on a machine that's now off).
            machine.cpu_percent = 0.0
            machine.ram_percent = 0.0
            machine.disk_percent = 0.0
            machine.idle_seconds = None
            db.commit()


async def _handshake(ws: WebSocket) -> dict | None:
    hello_raw = await ws.receive_text()
    hello = json.loads(hello_raw)

    machine = await run_in_threadpool(_fetch_machine, hello.get("machine_uid"))
    if machine is None or not machine["paired"]:
        await ws.close(code=4001, reason="unknown machine")
        return None

    nonce = secrets.token_hex(16)
    await ws.send_text(json.dumps({"type": "challenge", "nonce": nonce}))

    reply_raw = await ws.receive_text()
    reply = json.loads(reply_raw)
    ok = verify_agent_challenge(machine["machine_uid"], machine["secret"], nonce, reply.get("signature", ""))
    if not ok:
        await ws.close(code=4003, reason="bad signature")
        return None

    return machine


@router.websocket("/ws/agent")
async def agent_socket(ws: WebSocket):
    await ws.accept()
    machine: dict | None = None
    try:
        machine = await _handshake(ws)
        if machine is None:
            return

        await run_in_threadpool(_mark_online, machine["id"])
        await manager.connect(machine["id"], ws)

        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "status":
                await run_in_threadpool(
                    _update_status, machine["id"],
                    msg.get("cpu"), msg.get("ram"), msg.get("disk"), msg.get("os"), msg.get("ip"),
                    msg.get("idle"),
                )

            elif msg_type == "ack":
                await run_in_threadpool(
                    _update_ack, uuid.UUID(msg["command_id"]), msg.get("success"), msg.get("result"),
                )

    except WebSocketDisconnect:
        pass
    finally:
        if machine is not None:
            manager.disconnect(machine["id"])
            await run_in_threadpool(_mark_offline, machine["id"])
