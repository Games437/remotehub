"""
Two-way chat window. Unlike send_message()'s one-shot dialog, this stays
open across multiple messages — created lazily on the first incoming
chat message, reused for every one after that.

Runs as a Toplevel on the agent's single shared Tkinter thread (see
ui_thread.py) rather than spinning up its own independent Tk() root —
having more than one of those across separate threads is what used to
make the whole agent process crash unpredictably.

Outgoing replies go over a plain HTTP POST (not back through the
websocket) — simpler than bridging a reply back into the asyncio loop,
and just as valid since the reply doesn't need to share a connection
with anything else.
"""
import threading
import time

import requests

from agent import config, ui_thread
from agent.security import sign_chat_reply

_state = {
    "window": None,
    "text_area": None,
    "entry": None,
    "machine_uid": None,
    "secret": None,
}


def push_incoming(message: str, machine_uid: str, secret: str) -> None:
    """Called from the asyncio thread when a chat message arrives from
    the dashboard. Opens the window on first use."""
    _state["machine_uid"] = machine_uid
    _state["secret"] = secret
    ui_thread.run_on_ui_thread(lambda root: _show_message(root, "Admin: ", message))


def _send_reply(message: str) -> None:
    """Runs in its own short-lived thread so a slow/failed network call
    doesn't freeze the shared UI thread."""
    def _do_send():
        try:
            timestamp = int(time.time())
            nonce = str(int(time.time() * 1000))
            signature = sign_chat_reply(_state["secret"], message, timestamp, nonce)
            requests.post(
                f"{config.SERVER_HTTP_URL}/api/v1/agent/chat/reply",
                json={
                    "machine_uid": _state["machine_uid"],
                    "message": message,
                    "timestamp": timestamp,
                    "nonce": nonce,
                    "signature": signature,
                },
                timeout=10,
            )
        except Exception:
            pass  # best-effort — the admin will just see the reply missing from history

    threading.Thread(target=_do_send, daemon=True).start()


def _ensure_window(root) -> None:
    import tkinter as tk

    if _state["window"] is not None:
        try:
            _state["window"].winfo_exists()
            return
        except Exception:
            pass  # window was closed — fall through and rebuild it

    window = tk.Toplevel(root)
    window.title("RemoteHub — Chat")
    window.attributes("-topmost", True)
    window.geometry("340x400")
    window.configure(bg="#14161b")

    def on_close():
        window.destroy()
        _state["window"] = None

    window.protocol("WM_DELETE_WINDOW", on_close)

    text_area = tk.Text(
        window, state="disabled", wrap="word", bg="#1c1f26", fg="#E6E8EC",
        font=("Segoe UI", 10), relief="flat", padx=8, pady=8,
    )
    text_area.pack(fill="both", expand=True, padx=10, pady=(10, 6))

    entry_frame = tk.Frame(window, bg="#14161b")
    entry_frame.pack(fill="x", padx=10, pady=(0, 10))

    entry = tk.Entry(entry_frame, font=("Segoe UI", 10), bg="#1c1f26", fg="#E6E8EC",
                      insertbackground="#E6E8EC", relief="flat")
    entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 6))

    def on_send(_event=None):
        message = entry.get().strip()
        if not message:
            return
        entry.delete(0, "end")
        _append_line(text_area, "You: ", message)
        _send_reply(message)

    send_button = tk.Button(
        entry_frame, text="Send", command=on_send, bg="#5B8DEF", fg="white",
        relief="flat", font=("Segoe UI", 10), cursor="hand2",
    )
    send_button.pack(side="right")
    entry.bind("<Return>", on_send)
    entry.focus_set()

    _state["window"] = window
    _state["text_area"] = text_area
    _state["entry"] = entry


def _append_line(text_area, prefix: str, text: str) -> None:
    text_area.configure(state="normal")
    text_area.insert("end", f"{prefix}{text}\n")
    text_area.configure(state="disabled")
    text_area.see("end")


def _show_message(root, prefix: str, message: str) -> None:
    _ensure_window(root)
    _state["window"].deiconify()
    _state["window"].lift()
    _append_line(_state["text_area"], prefix, message)
