"""
Power / session commands. Written for Windows (per the original spec —
pywin32 + `shutdown.exe`), each function degrades to a clear error on other
platforms rather than silently doing nothing.
"""
import platform
import subprocess

DEFAULT_GRACE_SECONDS = 60


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _notify_local(title: str, message: str) -> None:
    """Best-effort local toast — used so the person at the keyboard (if any)
    sees this coming, since the operator sending the command has no live
    view of the screen to warn them any other way."""
    try:
        from plyer import notification

        notification.notify(title=title, message=message, app_name="RemoteHub")
    except Exception:
        pass  # notification is a courtesy, never block the actual action on it


def lock() -> dict:
    if not _is_windows():
        return {"ok": False, "error": "lock() is implemented for Windows only"}
    import ctypes

    ctypes.windll.user32.LockWorkStation()
    return {"ok": True}


def shutdown(payload: dict | None = None) -> dict:
    if not _is_windows():
        return {"ok": False, "error": "shutdown() is implemented for Windows only"}
    delay = int((payload or {}).get("delay_seconds", DEFAULT_GRACE_SECONDS))
    _notify_local("RemoteHub", f"This computer will shut down in {delay} seconds. "
                                f"Save your work now — an admin can still cancel it remotely.")
    subprocess.run(["shutdown", "/s", "/t", str(delay)], check=False)
    return {"ok": True, "delay_seconds": delay}


def restart(payload: dict | None = None) -> dict:
    if not _is_windows():
        return {"ok": False, "error": "restart() is implemented for Windows only"}
    delay = int((payload or {}).get("delay_seconds", DEFAULT_GRACE_SECONDS))
    _notify_local("RemoteHub", f"This computer will restart in {delay} seconds. "
                                f"Save your work now — an admin can still cancel it remotely.")
    subprocess.run(["shutdown", "/r", "/t", str(delay)], check=False)
    return {"ok": True, "delay_seconds": delay}


def cancel_shutdown() -> dict:
    """Cancels a pending shutdown/restart scheduled by the two functions above."""
    if not _is_windows():
        return {"ok": False, "error": "cancel_shutdown() is implemented for Windows only"}
    result = subprocess.run(["shutdown", "/a"], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        # exit code 1116 means "no shutdown was in progress" — not a real failure
        return {"ok": True, "note": "no shutdown/restart was pending"}
    _notify_local("RemoteHub", "The scheduled shutdown/restart was cancelled.")
    return {"ok": True}


def sleep() -> dict:
    if not _is_windows():
        return {"ok": False, "error": "sleep() is implemented for Windows only"}
    import ctypes

    # SetSuspendState(Hibernate=False, Force=False, DisableWakeEvent=False)
    ctypes.windll.powrprof.SetSuspendState(False, True, False)
    return {"ok": True}


def kill_process(payload: dict | None = None) -> dict:
    """payload = {"pid": 1234}. Takes a PID rather than a process name —
    names collide across instances (a machine can have a dozen chrome.exe
    processes), a PID is unambiguous."""
    pid = (payload or {}).get("pid")
    if pid is None:
        return {"ok": False, "error": "payload must include 'pid'"}

    try:
        import psutil

        proc = psutil.Process(int(pid))
        name = proc.name()
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except psutil.TimeoutExpired:
            proc.kill()  # didn't exit gracefully — force it
        return {"ok": True, "pid": int(pid), "name": name}
    except psutil.NoSuchProcess:
        return {"ok": False, "error": f"no process with pid {pid} (it may have already exited)"}
    except psutil.AccessDenied:
        return {"ok": False, "error": f"access denied terminating pid {pid} (needs admin rights)"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
