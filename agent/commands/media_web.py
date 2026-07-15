import glob
import os
import platform
import shutil
import subprocess
import webbrowser

# Common human-friendly names -> the actual .exe filename Windows knows
# them by. Needed because e.g. "word" is not WINWORD.EXE's real name, so
# neither PATH search nor the App Paths registry would ever match it
# without this translation.
PROGRAM_ALIASES = {
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE",
    "outlook": "OUTLOOK.EXE",
    "onenote": "ONENOTE.EXE",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "firefox": "firefox.exe",
    "spotify": "Spotify.exe",
    "discord": "Discord.exe",
    "vscode": "Code.exe",
    "vs code": "Code.exe",
    "code": "Code.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "task manager": "taskmgr.exe",
    "control panel": "control.exe",
}

# Some installers (mostly games/launchers) don't register a Windows "App
# Paths" entry and don't add themselves to PATH either, so neither of our
# normal lookup methods can ever find them — no matter how the alias table
# translates the name. For these we keep a list of known install-path
# patterns to check directly. Patterns support env vars (%LocalAppData%
# etc.) and glob wildcards, since some (like Roblox) install into a
# version-numbered folder that changes on every update.
PROGRAM_FALLBACK_PATHS: dict[str, list[str]] = {
    "steam": [
        r"%ProgramFiles(x86)%\Steam\Steam.exe",
        r"%ProgramFiles%\Steam\Steam.exe",
    ],
    "roblox": [
        r"%LocalAppData%\Roblox\Versions\*\RobloxPlayerBeta.exe",
    ],
}


def _find_via_fallback_paths(lookup_name: str) -> str | None:
    """Checks PROGRAM_FALLBACK_PATHS for hardcoded/glob install locations —
    the last resort for programs that skip Windows' usual registration
    conventions entirely."""
    patterns = PROGRAM_FALLBACK_PATHS.get(lookup_name)
    if not patterns:
        return None

    for pattern in patterns:
        expanded = os.path.expandvars(pattern)
        matches = glob.glob(expanded)
        if matches:
            # For version-numbered folders (e.g. Roblox), the most recently
            # modified match is the current install.
            matches.sort(key=os.path.getmtime, reverse=True)
            return matches[0]
    return None


def _find_via_app_paths(exe_name: str) -> str | None:
    """Looks up an exact .exe filename in the Windows "App Paths" registry —
    this is what most installers register, and covers non-default install
    locations. `exe_name` must be the real filename (e.g. "WINWORD.EXE")."""
    try:
        import winreg
    except ImportError:
        return None  # not on Windows

    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            key = winreg.OpenKey(
                hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}"
            )
            path, _ = winreg.QueryValueEx(key, "")
            if path and os.path.exists(path):
                return path
        except OSError:
            continue
    return None


def _find_chrome() -> str | None:
    resolved = _find_via_app_paths("chrome.exe")
    if resolved:
        return resolved

    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _resolve_program(name: str) -> str | None:
    """
    Tries to find a real, launchable path for a bare program name (e.g.
    "word", "chrome", "notepad", "steam"), checking — in order — the
    alias table + PATH, the App Paths registry, and finally the hardcoded
    fallback paths for programs that don't follow either convention.
    Returns None if nothing matches, so the caller can report a clean
    error instead of letting Windows pop up its own "cannot find" dialog
    on the remote screen.
    """
    lookup_name = name.strip().lower()
    exe_name = PROGRAM_ALIASES.get(lookup_name, name)

    candidates = [exe_name]
    if not exe_name.lower().endswith(".exe"):
        candidates.append(f"{exe_name}.exe")

    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found

    for candidate in candidates:
        found = _find_via_app_paths(candidate)
        if found:
            return found

    found = _find_via_fallback_paths(lookup_name)
    if found:
        return found

    return None


def _normalize_url(raw: str) -> str:
    """Turns a bare site name into a full URL: "youtube" -> "https://youtube.com"."""
    raw = raw.strip()
    if "://" in raw:
        return raw
    if "." not in raw:
        raw = f"{raw}.com"
    return f"https://{raw}"


def open_website(payload: dict) -> dict:
    site = (payload or {}).get("url")
    if not site:
        return {"ok": False, "error": "missing 'url' in payload"}

    url = _normalize_url(site)
    chrome_path = _find_chrome()

    if chrome_path:
        try:
            subprocess.Popen([chrome_path, url])
            return {"ok": True}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    # Chrome isn't installed on this agent — fall back to whatever the OS
    # default is, but say so, since the person asked for Chrome specifically.
    webbrowser.open(url)
    return {"ok": True, "warning": "Chrome not found on this machine; opened with the default browser instead"}


def open_program(payload: dict) -> dict:
    name = (payload or {}).get("path")
    if not name:
        return {"ok": False, "error": "missing 'path' in payload"}

    # A full path was given — launch it directly, same as before.
    if os.path.isabs(name) or os.path.sep in name:
        try:
            subprocess.Popen([name])
            return {"ok": True}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    # Just a bare name (e.g. "chrome", "word", "notepad") — resolve it
    # ourselves via aliases/PATH/App Paths. We deliberately do NOT fall
    # back to Windows' `start` command here: when it can't find something,
    # it pops up its own "Windows cannot find ..." dialog directly on the
    # remote machine's screen, which is confusing and gives no useful
    # error back to the dashboard.
    resolved = _resolve_program(name)
    if not resolved:
        return {"ok": False, "error": f"Could not find a program matching '{name}' on this machine"}

    try:
        subprocess.Popen([resolved])
        return {"ok": True}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def play_music(payload: dict) -> dict:
    """Opens a track/playlist URL (Spotify/YouTube link, or a local file path) with the OS default handler."""
    target = (payload or {}).get("url") or (payload or {}).get("path")
    if not target:
        return {"ok": False, "error": "missing 'url' or 'path' in payload"}
    webbrowser.open(target)
    return {"ok": True}


def notify(payload: dict) -> dict:
    title = (payload or {}).get("title", "RemoteHub")
    message = (payload or {}).get("message", "")
    try:
        from plyer import notification

        notification.notify(title=title, message=message, app_name="RemoteHub")
    except Exception as exc:  # plyer backend availability varies by OS
        return {"ok": False, "error": str(exc)}
    return {"ok": True}


def send_message(payload: dict) -> dict:
    """A dialog the user must click OK to dismiss, styled and clearly
    labeled as coming from an admin — unlike `notify()` above, which is an
    unstyled toast that disappears on its own whether or not anyone saw it.

    Runs in its own thread rather than blocking here: the native
    MessageBoxW this used to call blocks the calling thread until the
    person clicks OK, which could stall this agent's command handling
    indefinitely if nobody's at the keyboard. This acknowledges as soon as
    the dialog is *shown*, not once it's dismissed.
    """
    if platform.system() != "Windows":
        return {"ok": False, "error": "send_message() is implemented for Windows only"}

    message = (payload or {}).get("message", "")
    if not message:
        return {"ok": False, "error": "payload must include 'message'"}

    def _show_dialog():
        import tkinter as tk

        root = tk.Tk()
        root.title("RemoteHub")
        root.attributes("-topmost", True)
        root.resizable(False, False)
        root.configure(bg="#14161b")

        width, height = 380, 200
        x = (root.winfo_screenwidth() - width) // 2
        y = (root.winfo_screenheight() - height) // 2
        root.geometry(f"{width}x{height}+{x}+{y}")

        tk.Label(
            root, text="Message from Admin", font=("Segoe UI", 13, "bold"),
            bg="#14161b", fg="#5B8DEF",
        ).pack(pady=(20, 6), padx=20, anchor="w")

        tk.Label(
            root, text=message, font=("Segoe UI", 10), bg="#14161b", fg="#E6E8EC",
            wraplength=336, justify="left",
        ).pack(pady=(0, 20), padx=20, anchor="w")

        tk.Button(
            root, text="OK", command=root.destroy, width=10,
            bg="#5B8DEF", fg="white", activebackground="#4a78d4",
            relief="flat", font=("Segoe UI", 10), cursor="hand2",
        ).pack(pady=(0, 20))

        root.mainloop()

    try:
        import threading
        threading.Thread(target=_show_dialog, daemon=True).start()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    return {"ok": True}


def clipboard(payload: dict) -> dict:
    """payload = {"action": "get"} or {"action": "set", "text": "..."}"""
    try:
        import pyperclip
    except ImportError:
        return {"ok": False, "error": "pyperclip is not installed on this agent"}

    action = (payload or {}).get("action", "get")
    if action == "set":
        pyperclip.copy((payload or {}).get("text", ""))
        return {"ok": True}
    return {"ok": True, "text": pyperclip.paste()}