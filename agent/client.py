"""
RemoteHub agent.

Normal flow: the GUI calls login() with the user's email + password. The
first time this machine ever logs in, it registers itself under the
account (one new Machine row). Every login after that just re-authenticates
the user and reuses the machine identity already saved locally — it never
creates a second Machine row for the same install.

Pairing-code flow (kept as an option for shared/customer machines where
typing the account password on that machine isn't appropriate):

    python -m agent.client pair ABCD-EFGH     # one-time pairing, then exits

`start_agent_loop()` connects to the server over a websocket, completes
the Layer 3 challenge/response handshake, then loops: send periodic
status reports, receive+execute commands, verify+ack each one.
`stop_agent_loop()` cleanly tears that connection down (used by Logout).
"""
import asyncio
import json
import platform
import socket
import sys
import threading
import time

import psutil
import requests
import websockets

from agent import config
from agent.commands import DISPATCH
from agent.security import sign_challenge, verify_command

STATUS_INTERVAL_SECONDS = 15

_status_callback = None  # set by the GUI; called with "connecting" | "connected" | "disconnected" | "error:<msg>"
_stop_event = threading.Event()


def pair(code: str) -> None:
    resp = requests.post(f"{config.SERVER_HTTP_URL}/api/v1/machines/pair/redeem", json={"code": code}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    config.save_credentials(data["machine_uid"], data["secret"])
    print(f"Paired successfully as machine {data['machine_uid']}. Credentials saved locally.")


def login(email: str, password: str) -> tuple[bool, str]:
    """
    Authenticates as the user. If this machine has never been registered
    before, also registers it (one time only). If it's already registered
    (saved credentials exist locally), just verifies the password and
    reuses the existing machine identity — never creates a duplicate.
    Never raises — always returns (success, message) so the GUI can show it.
    """
    try:
        login_resp = requests.post(
            f"{config.SERVER_HTTP_URL}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
    except requests.RequestException as exc:
        return False, f"Cannot reach server: {exc}"

    if login_resp.status_code == 401:
        detail = login_resp.json().get("detail", "Incorrect email or password")
        return False, detail
    try:
        login_resp.raise_for_status()
    except requests.HTTPError as exc:
        return False, f"Login failed: {exc}"

    # Already registered on this machine — password verified, nothing else to do.
    if config.load_credentials() is not None:
        return True, "Logged in"

    access_token = login_resp.json()["access_token"]

    try:
        reg_resp = requests.post(
            f"{config.SERVER_HTTP_URL}/api/v1/machines/register",
            json={"hostname": socket.gethostname(), "os": f"{platform.system()} {platform.release()}"},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        reg_resp.raise_for_status()
    except requests.RequestException as exc:
        return False, f"Machine registration failed: {exc}"

    data = reg_resp.json()
    config.save_credentials(data["machine_uid"], data["secret"])
    return True, "Logged in and registered"


def pair_with_code(code: str) -> tuple[bool, str]:
    """Same as pair(), but returns (success, message) instead of raising — for GUI use."""
    try:
        pair(code)
        return True, "Paired successfully"
    except requests.HTTPError:
        return False, "Invalid or expired pairing code"
    except requests.RequestException as exc:
        return False, f"Cannot reach server: {exc}"


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "unknown"


def _collect_status() -> dict:
    return {
        "type": "status",
        "cpu": psutil.cpu_percent(interval=None),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage("/").percent,
        "os": f"{platform.system()} {platform.release()}",
        "ip": _local_ip(),
    }


def _report_status(state: str) -> None:
    if _status_callback is not None:
        try:
            _status_callback(state)
        except Exception:
            pass  # never let a broken GUI callback take down the agent loop


async def _handle_command(ws, secret: str, msg: dict) -> None:
    command_type = msg["command_type"]
    ok, reason = verify_command(secret, command_type, msg["timestamp"], msg["nonce"], msg["signature"])
    if not ok:
        await ws.send(json.dumps({"type": "ack", "command_id": msg["command_id"], "success": False,
                                   "result": {"error": f"rejected: {reason}"}}))
        return

    handler = DISPATCH.get(command_type)
    if handler is None:
        result = {"error": f"unknown command_type '{command_type}'"}
        success = False
    else:
        try:
            # 🌟 ส่วนที่แก้ไข/เพิ่มเงื่อนไขพิเศษสำหรับ screenshot เข้าไปตรงนี้ครับ
            if command_type == "screenshot":
                from PIL import ImageGrab
                import io
                import base64
                
                # 1. สั่งถ่ายภาพหน้าจอเครื่อง Agent
                screenshot = ImageGrab.grab()
                
                # 2. แปลงรูปภาพเป็น Bytes ไว้ในหน่วยความจำ
                buffer = io.BytesIO()
                screenshot.save(buffer, format="PNG")
                img_bytes = buffer.getvalue()
                
                # 3. เข้ารหัสเป็น Base64 String 
                img_b64 = base64.b64encode(img_bytes).decode('utf-8')
                
                # 4. กำหนดผลลัพธ์ใส่ตัวแปร result 
                result = {"ok": True, "image_b64": img_b64}
                success = True
            else:
                # คำสั่งอื่นๆ (เช่น open_website) ให้ทำงานผ่าน handler ดั้งเดิมตามปกติ
                result = handler(msg.get("payload"))
                success = bool(result.get("ok", True))
                
        except Exception as exc:
            result = {"error": str(exc)}
            success = False

    # ส่งก้อนผลลัพธ์ที่มีก้อนภาพหลุดกลับไปให้เซิร์ฟเวอร์
    await ws.send(json.dumps({"type": "ack", "command_id": msg["command_id"], "success": success, "result": result}))


async def _run() -> None:
    creds = config.load_credentials()
    if creds is None:
        print("Not paired yet.")
        _report_status("error:not paired")
        return

    machine_uid, secret = creds["machine_uid"], creds["secret"]

    async for ws in websockets.connect(config.SERVER_WS_URL):
        if _stop_event.is_set():
            break
        try:
            print(f"Connecting as {machine_uid}...")
            _report_status("connecting")

            await ws.send(json.dumps({"machine_uid": machine_uid}))
            challenge = json.loads(await ws.recv())
            nonce = challenge["nonce"]
            signature = sign_challenge(machine_uid, secret, nonce)
            await ws.send(json.dumps({"signature": signature}))
            print("Connected. Waiting for commands... (Ctrl+C to stop)")
            _report_status("connected")

            last_status = 0.0

            while True:
                if _stop_event.is_set():
                    await ws.close()
                    return

                now = time.monotonic()
                if now - last_status > STATUS_INTERVAL_SECONDS:
                    status = _collect_status()
                    await ws.send(json.dumps(status))
                    print(f"  status sent — cpu {status['cpu']}% ram {status['ram']}% disk {status['disk']}%")
                    last_status = now

                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                msg = json.loads(raw)
                if msg.get("type") == "command":
                    print(f"  received command: {msg.get('command_type')}")
                    await _handle_command(ws, secret, msg)

        except websockets.ConnectionClosed as exc:
            if _stop_event.is_set():
                return

            close_code = getattr(exc, "code", None) or getattr(getattr(exc, "rcvd", None), "code", None)
            if close_code in (4001, 4003):
                # 4001 = server no longer recognizes this machine_uid (it was
                # removed from the dashboard); 4003 = signature rejected
                # (secret no longer matches, e.g. machine was re-issued).
                # Retrying forever would just hammer the server, since the
                # credentials are permanently invalid — forget them locally
                # and require the user to log in again.
                reason = "removed from your account" if close_code == 4001 else "credentials rejected"
                print(f"This machine was {reason} by the server. Clearing local credentials.")
                config.clear_credentials()
                _report_status(f"removed:{reason}")
                return

            print(f"Disconnected ({exc}), retrying in a moment...")
            _report_status("disconnected")
            continue
        except Exception as exc:
            if _stop_event.is_set():
                return
            print(f"Unexpected error: {exc!r}, retrying in a moment...")
            _report_status(f"error:{exc}")
            await asyncio.sleep(3)
            continue

    _report_status("disconnected")


def start_agent_loop(on_status=None) -> bool:
    """Starts the background websocket loop. Returns False if not paired/registered yet."""
    global _status_callback
    creds = config.load_credentials()
    if creds is None:
        return False

    _status_callback = on_status
    _stop_event.clear()

    def _runner():
        asyncio.run(_run())

    threading.Thread(target=_runner, daemon=True).start()
    return True


def stop_agent_loop() -> None:
    """Used by Logout: cleanly closes the websocket and stops the loop.
    Machine identity (pair.json) is kept — only the live connection stops."""
    _stop_event.set()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "pair":
        pair(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == "run":
        asyncio.run(_run())
    else:
        print(__doc__)