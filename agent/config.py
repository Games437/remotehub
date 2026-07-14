"""
Local agent configuration.

`pair.json` holds this machine's permanent identity (machine_uid + secret),
written once after pairing/registration and reused for the lifetime of the
install. `settings.json` holds small local preferences (currently just the
"remember me" flag) that are safe to store in plaintext.

Both files live under %APPDATA%\\RemoteHub\\ rather than next to this script.
This matters a lot for a onefile PyInstaller build: at runtime `__file__`
resolves to a temporary extraction folder (_MEIxxxxx) that Windows deletes
the moment the process exits, so anything saved next to the script would
silently vanish every time the app is closed. %APPDATA% is a stable,
per-user, writable-without-admin location that survives restarts.
"""
import json
import os

#SERVER_HTTP_URL = os.environ.get("REMOTEHUB_SERVER_HTTP", "http://localhost:8000")
#SERVER_WS_URL = os.environ.get("REMOTEHUB_SERVER_WS", "ws://localhost:8000/ws/agent")
SERVER_HTTP_URL = os.environ.get("REMOTEHUB_SERVER_HTTP", "https://remotehub-backend-1lqx.onrender.com")
SERVER_WS_URL = os.environ.get("REMOTEHUB_SERVER_WS", "wss://remotehub-backend-1lqx.onrender.com/ws/agent")

_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "RemoteHub")
os.makedirs(_DATA_DIR, exist_ok=True)

_CREDENTIALS_PATH = os.path.join(_DATA_DIR, "pair.json")
_SETTINGS_PATH = os.path.join(_DATA_DIR, "settings.json")


# ---------------------------------------------------------------------------
# Machine identity (machine_uid + secret) — set once, kept for the life of
# the install. Logging out does NOT clear this; only "remove this device"
# would.
# ---------------------------------------------------------------------------
def load_credentials() -> dict | None:
    if not os.path.exists(_CREDENTIALS_PATH):
        return None
    with open(_CREDENTIALS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_credentials(machine_uid: str, secret: str) -> None:
    with open(_CREDENTIALS_PATH, "w", encoding="utf-8") as f:
        json.dump({"machine_uid": machine_uid, "secret": secret}, f)
    try:
        os.chmod(_CREDENTIALS_PATH, 0o600)
    except OSError:
        pass  # chmod is a no-op on some Windows filesystems; ACLs should be set at install time instead


def clear_credentials() -> None:
    """Fully forgets this machine's identity. NOT called by logout — only
    intended for an explicit 'remove/reset this device' action."""
    if os.path.exists(_CREDENTIALS_PATH):
        os.remove(_CREDENTIALS_PATH)


# ---------------------------------------------------------------------------
# Local preferences ("remember me")
# ---------------------------------------------------------------------------
def _load_settings() -> dict:
    if not os.path.exists(_SETTINGS_PATH):
        return {}
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_settings(data: dict) -> None:
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


def load_remember() -> bool:
    return bool(_load_settings().get("remember", False))


def load_last_email() -> str:
    return _load_settings().get("last_email", "")


def save_remember(remember: bool, email: str | None = None) -> None:
    """We never store the password itself — only whether this device is
    trusted to auto-connect, plus the email as a convenience prefill."""
    data = _load_settings()
    data["remember"] = remember
    if remember and email:
        data["last_email"] = email
    if not remember:
        data.pop("last_email", None)
    _save_settings(data)