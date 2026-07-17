"""
Remote file browsing — list a folder's contents, then fetch a specific
file back as base64 (same pattern the screenshot command already uses to
return binary data through a JSON command result).
"""
import base64
import os
import string

_MAX_FETCH_BYTES = 15 * 1024 * 1024  # 15 MB — comfortably fits a JSON
# command result over the websocket; bigger than this and it's a job for
# a real file-transfer tool, not a remote-admin command result.


def _list_drives() -> list[str]:
    """Every mounted drive letter (C:\\, D:\\, ...) — included in every
    list_folder result so the dashboard can offer a way to jump to any
    drive, not just wherever the current path happens to be."""
    try:
        import ctypes
        drives = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i, letter in enumerate(string.ascii_uppercase):
            if bitmask & (1 << i):
                drives.append(f"{letter}:\\")
        return drives
    except Exception:
        return []  # non-Windows or the call failed — just show no drive shortcuts, not fatal


def list_folder(payload: dict | None = None) -> dict:
    """payload = {"path"?: str}. Defaults to the user's home folder if no
    path is given — a reasonable starting point rather than erroring out
    or picking something arbitrary like C:\\."""
    path = (payload or {}).get("path") or os.path.expanduser("~")

    if not os.path.isdir(path):
        return {"ok": False, "error": f"'{path}' is not a folder (or doesn't exist)"}

    entries = []
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    is_dir = entry.is_dir()
                    size = None if is_dir else entry.stat().st_size
                    entries.append({"name": entry.name, "is_dir": is_dir, "size_bytes": size})
                except OSError:
                    continue  # permission-denied or a broken link mid-scan — skip it, not fatal
    except PermissionError:
        return {"ok": False, "error": f"access denied reading '{path}'"}

    entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
    normalized = os.path.normpath(path)
    parent = os.path.dirname(normalized)
    # No parent to go "up" to once we're at a drive root (dirname("C:\\")
    # is "C:\\" itself) — the frontend uses this to decide whether to show
    # a working Back button.
    has_parent = parent != normalized

    return {
        "ok": True,
        "path": normalized,
        "entries": entries,
        "parent": parent if has_parent else None,
        "drives": _list_drives(),
    }


def fetch_file(payload: dict) -> dict:
    """payload = {"path": str}. Returns the file's content base64-encoded
    — capped at _MAX_FETCH_BYTES so this can't be used to try to drag a
    multi-gigabyte file through a JSON command result."""
    path = (payload or {}).get("path")
    if not path:
        return {"ok": False, "error": "payload must include 'path'"}

    if not os.path.isfile(path):
        return {"ok": False, "error": f"'{path}' is not a file (or doesn't exist)"}

    try:
        size = os.path.getsize(path)
        if size > _MAX_FETCH_BYTES:
            return {
                "ok": False,
                "error": f"file is {round(size / 1024 / 1024, 1)} MB — over the "
                         f"{_MAX_FETCH_BYTES // 1024 // 1024} MB limit for a single fetch",
            }
        with open(path, "rb") as f:
            content = f.read()
    except PermissionError:
        return {"ok": False, "error": f"access denied reading '{path}'"}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    return {
        "ok": True,
        "filename": os.path.basename(path),
        "size_bytes": size,
        "content_base64": base64.b64encode(content).decode("ascii"),
    }
