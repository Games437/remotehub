"""
Tracks live agent connections in-process and pushes commands to them.

For a multi-replica deployment, an agent might be connected to a different
backend instance than the one handling the REST request that issues a
command. In that case, publish the command over Redis pub/sub instead
(settings.USE_REDIS) and have every replica subscribe + forward to any
locally-connected agent matching the machine_id. The single-process version
below is intentionally simple for local dev / small deployments.
"""
import json
import uuid

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, machine_id: uuid.UUID, ws: WebSocket) -> None:
        # NOTE: the socket is already accepted (and handshaken) by the
        # caller in agent_ws.py before this is called — do not call
        # ws.accept() again here, it would raise.
        self._connections[str(machine_id)] = ws

    def disconnect(self, machine_id: uuid.UUID) -> None:
        self._connections.pop(str(machine_id), None)

    def is_online(self, machine_id: uuid.UUID) -> bool:
        return str(machine_id) in self._connections

    async def send_command(self, machine_id: uuid.UUID, message: dict) -> bool:
        ws = self._connections.get(str(machine_id))
        if ws is None:
            return False
        await ws.send_text(json.dumps(message))
        return True


manager = ConnectionManager()