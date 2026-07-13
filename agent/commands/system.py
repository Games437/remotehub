"""
Power / session commands. Written for Windows (per the original spec —
pywin32 + `shutdown.exe`), each function degrades to a clear error on other
platforms rather than silently doing nothing.
"""
import platform
import subprocess


def _is_windows() -> bool:
    return platform.system() == "Windows"


def lock() -> dict:
    if not _is_windows():
        return {"ok": False, "error": "lock() is implemented for Windows only"}
    import ctypes

    ctypes.windll.user32.LockWorkStation()
    return {"ok": True}


def shutdown() -> dict:
    if not _is_windows():
        return {"ok": False, "error": "shutdown() is implemented for Windows only"}
    subprocess.run(["shutdown", "/s", "/t", "0"], check=False)
    return {"ok": True}


def restart() -> dict:
    if not _is_windows():
        return {"ok": False, "error": "restart() is implemented for Windows only"}
    subprocess.run(["shutdown", "/r", "/t", "0"], check=False)
    return {"ok": True}


def sleep() -> dict:
    if not _is_windows():
        return {"ok": False, "error": "sleep() is implemented for Windows only"}
    import ctypes

    # SetSuspendState(Hibernate=False, Force=False, DisableWakeEvent=False)
    ctypes.windll.powrprof.SetSuspendState(False, True, False)
    return {"ok": True}
