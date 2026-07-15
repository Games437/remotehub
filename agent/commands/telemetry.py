"""
Read-only "what's going on" commands. These never change anything on the
machine — they just report back, which is the main substitute for not
having a live view of the screen: instead of looking, you ask.
"""
import platform


def get_idle_time() -> dict:
    """How long since the last keyboard/mouse input — the main signal for
    'is anyone actually sitting at this machine right now' before you send
    something disruptive like shutdown."""
    if platform.system() != "Windows":
        return {"ok": False, "error": "get_idle_time() is implemented for Windows only"}

    import ctypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return {"ok": False, "error": "GetLastInputInfo failed"}

    idle_ms = ctypes.windll.kernel32.GetTickCount() - info.dwTime
    return {"ok": True, "idle_seconds": round(idle_ms / 1000, 1)}


def list_processes() -> dict:
    """Processes grouped by name — enough to answer 'what's actually running
    right now' without needing to see the desktop, and without a wall of
    50 near-identical chrome.exe rows to scroll through."""
    try:
        import psutil
    except ImportError:
        return {"ok": False, "error": "psutil is not installed on this agent"}

    # Windows system processes that are almost always running and almost
    # never what someone means by "what's open" — hidden unless they're
    # actually using enough resources to be worth flagging.
    _SYSTEM_NOISE = {
        "system idle process", "system", "registry", "memory compression",
        "csrss", "smss", "wininit", "winlogon", "services", "lsass",
        "svchost", "dwm", "fontdrvhost", "sihost", "conhost",
        "runtimebroker", "searchindexer", "searchprotocolhost", "audiodg",
        "spoolsv", "wmiprvse", "dllhost", "taskhostw",
    }
    _SYSTEM_NOISE_THRESHOLD_PERCENT = 1.0  # still show them if actually heavy

    groups: dict[str, dict] = {}
    total_process_count = 0

    for proc in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
        try:
            info = proc.info
            raw_name = info["name"] or "unknown"
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue  # process exited or is protected mid-scan — skip it, not fatal

        total_process_count += 1

        # Strip the .exe suffix for display — same process either way, just
        # less visual noise than every row ending the same way.
        display_name = raw_name[:-4] if raw_name.lower().endswith(".exe") else raw_name
        key = display_name.lower()

        group = groups.setdefault(key, {
            "name": display_name,
            "instance_count": 0,
            "memory_percent": 0.0,
            "cpu_percent": 0.0,
            "pids": [],
        })
        group["instance_count"] += 1
        group["memory_percent"] += info["memory_percent"] or 0
        group["cpu_percent"] += info["cpu_percent"] or 0
        # Kept so the dashboard can offer a one-click "kill" per instance
        # instead of making someone go find and type a PID by hand.
        group["pids"].append(info["pid"])

    visible_groups = []
    for key, group in groups.items():
        group["memory_percent"] = round(group["memory_percent"], 2)
        group["cpu_percent"] = round(group["cpu_percent"], 2)

        if key in _SYSTEM_NOISE and group["memory_percent"] < _SYSTEM_NOISE_THRESHOLD_PERCENT:
            continue  # background Windows plumbing using negligible resources — not useful to show

        visible_groups.append(group)

    visible_groups.sort(key=lambda g: g["memory_percent"], reverse=True)
    return {
        "ok": True,
        "processes": visible_groups[:40],
        "total_count": total_process_count,
        "grouped_count": len(visible_groups),
    }


def get_active_window() -> dict:
    """The window currently in focus — the main substitute for glancing at
    the screen to see what the user is actually doing right now."""
    if platform.system() != "Windows":
        return {"ok": False, "error": "get_active_window() is implemented for Windows only"}

    import ctypes

    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return {"ok": True, "title": None, "process_name": None, "pid": None}

    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)

    pid = ctypes.c_uint()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    process_name = None
    try:
        import psutil
        process_name = psutil.Process(pid.value).name()
    except Exception:
        pass  # process may have exited between the two calls, or access denied — not fatal

    return {"ok": True, "title": buffer.value, "process_name": process_name, "pid": pid.value}


def list_open_windows() -> dict:
    """Every visible top-level window with a title — the main substitute for
    glancing at the taskbar to see what's left open (and possibly unsaved)
    before a shutdown/restart."""
    if platform.system() != "Windows":
        return {"ok": False, "error": "list_open_windows() is implemented for Windows only"}

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    windows = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def _enum_handler(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True  # no title — background/helper window, not something a user has "open"

        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)

        pid = ctypes.c_uint()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        process_name = None
        try:
            import psutil
            process_name = psutil.Process(pid.value).name()
        except Exception:
            pass

        windows.append({
            "title": buffer.value,
            "process_name": process_name,
            "pid": pid.value,
            "minimized": bool(user32.IsIconic(hwnd)),
        })
        return True

    user32.EnumWindows(_enum_handler, 0)
    return {"ok": True, "windows": windows, "total_count": len(windows)}


def get_network_status() -> dict:
    """Whether this machine currently has a working internet connection —
    the main substitute for noticing 'huh, nothing's loading' on the screen."""
    import socket
    import time

    # Virtual/internal adapters (WSL, Hyper-V, Docker's own vEthernet,
    # loopback, ...) are almost always reported "up" regardless of whether
    # the machine has real internet access, and picking one of these to
    # display is misleading — it looks like a real NIC but isn't the actual
    # route to the internet. Filter them out and prefer a real adapter.
    _VIRTUAL_ADAPTER_MARKERS = (
        "loopback", "vethernet", "wsl", "hyper-v", "virtualbox",
        "vmware", "docker", "npcap", "teredo", "tap-", "tunnel",
    )

    def _looks_virtual(name: str) -> bool:
        lowered = name.lower()
        return any(marker in lowered for marker in _VIRTUAL_ADAPTER_MARKERS)

    interface = None
    try:
        import psutil
        stats = psutil.net_if_stats()
        real_up = [name for name, s in stats.items() if s.isup and not _looks_virtual(name)]
        if real_up:
            interface = real_up[0]
        else:
            # Nothing looked like a real adapter — fall back to whatever's
            # up rather than showing nothing, but this is a weaker signal.
            any_up = [name for name, s in stats.items() if s.isup and name.lower() != "loopback"]
            interface = any_up[0] if any_up else None
    except Exception:
        pass  # interface name is a nice-to-have, never block the actual connectivity check on it

    # Some networks filter or rate-limit raw DNS lookups (port 53) to
    # arbitrary external IPs even though normal browsing works fine —
    # port 443 (HTTPS) is a much more reliable signal of "can this machine
    # actually reach the internet" since that's what real traffic uses.
    start = time.monotonic()
    try:
        sock = socket.create_connection(("1.1.1.1", 443), timeout=3)
        sock.close()
        latency_ms = round((time.monotonic() - start) * 1000, 1)
        return {"ok": True, "connected": True, "latency_ms": latency_ms, "interface": interface}
    except OSError as exc:
        return {"ok": True, "connected": False, "latency_ms": None, "interface": interface, "error": str(exc)}


def _get_cpu_name() -> tuple[str | None, str | None]:
    """platform.processor() often returns a generic/truncated string on
    Windows (or just the raw family/model/stepping numbers) — the actual
    friendly name ("AMD Ryzen 7 5800X") lives in the registry. Returns
    (name, error) so a failure here is visible instead of silently falling
    back to the worse string with no explanation."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
        )
        name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
        return name.strip(), None
    except Exception as exc:
        return None, str(exc)


def _get_gpu_names() -> tuple[list[str], str | None]:
    """Queries WMI for video controllers — a machine can have more than one
    (integrated + discrete), so this returns all of them rather than just
    the first. Returns (names, error) — error is None on success, so the
    caller can tell "no GPUs found" apart from "the query itself failed".

    Explicit CoInitialize/CoUninitialize because this runs on the agent's
    single asyncio-loop thread, not a fresh worker thread — COM apartment
    state there isn't guaranteed, and without this the WMI call can fail
    silently depending on what else has (or hasn't) touched COM already.
    """
    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        try:
            wmi = win32com.client.GetObject("winmgmts:")
            adapters = wmi.ExecQuery("SELECT Name FROM Win32_VideoController")
            names = [a.Name for a in adapters if getattr(a, "Name", None)]
            return names, None
        finally:
            pythoncom.CoUninitialize()
    except Exception as exc:
        return [], str(exc)


def get_system_info() -> dict:
    """Static-ish machine specs — CPU, GPU, total RAM, per-drive disk
    capacity, OS version, uptime. Unlike the other telemetry commands this
    rarely changes, so there's no separate "disk usage" button: the
    per-drive breakdown just lives here instead of forcing a 13th button
    that would almost always show the same numbers as this one."""
    import platform as platform_module
    import socket
    import time

    info: dict = {
        "ok": True,
        "hostname": socket.gethostname(),
        "os": f"{platform_module.system()} {platform_module.release()}",
        "os_version": platform_module.version(),
    }

    cpu_name, cpu_error = _get_cpu_name()
    gpu_names, gpu_error = _get_gpu_names()
    info["cpu_model"] = cpu_name or platform_module.processor() or None
    info["gpu"] = gpu_names
    if cpu_error:
        info["cpu_lookup_error"] = cpu_error
    if gpu_error:
        info["gpu_lookup_error"] = gpu_error

    try:
        import psutil

        info["cpu_cores"] = psutil.cpu_count(logical=False)
        info["cpu_threads"] = psutil.cpu_count(logical=True)

        mem = psutil.virtual_memory()
        info["ram_total_gb"] = round(mem.total / (1024 ** 3), 1)

        info["uptime_seconds"] = int(time.time() - psutil.boot_time())

        drives = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue  # e.g. an empty CD/DVD drive letter — skip, not fatal
            drives.append({
                "drive": part.device,
                "total_gb": round(usage.total / (1024 ** 3), 1),
                "used_gb": round(usage.used / (1024 ** 3), 1),
                "percent": usage.percent,
            })
        info["drives"] = drives
    except Exception as exc:
        info["partial_error"] = str(exc)  # hostname/os/cpu/gpu still returned even if psutil hiccups

    return info
