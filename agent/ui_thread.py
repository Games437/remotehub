"""
Single shared Tkinter thread for the whole agent.

Tcl/Tk is not safe with multiple independent Tk() root instances running
on separate OS threads within one process — earlier versions of this
agent created one ad-hoc Tk() per feature (send_message's dialog, the
chat window), each on its own throwaway thread. That combination is
exactly the kind of thing that crashes the whole interpreter
unpredictably, not just the one feature that was using it — which
matches "sometimes the whole program just closes" being reported.

Everything that needs a window now goes through this one shared root
instead, as a Toplevel, scheduled via a thread-safe queue rather than
touching Tkinter directly from whatever thread happens to need it.
"""
import queue
import threading

_work_queue: "queue.Queue" = queue.Queue()
_thread: threading.Thread | None = None
_started = threading.Event()


def run_on_ui_thread(fn) -> None:
    """fn(root) will be called on the shared Tkinter thread, where root is
    the one persistent (hidden) Tk() instance. Safe to call from any
    thread — this only ever queues the work, never touches Tkinter
    directly from the calling thread."""
    _ensure_started()
    _work_queue.put(fn)


def _ensure_started() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _thread = threading.Thread(target=_run, daemon=True)
    _thread.start()
    _started.wait(timeout=5)


def _run() -> None:
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()  # this root itself is never shown — real windows are Toplevels on it

    def poll():
        try:
            while True:
                fn = _work_queue.get_nowait()
                try:
                    fn(root)
                except Exception:
                    pass  # one broken window shouldn't take down the shared UI thread
        except queue.Empty:
            pass
        root.after(100, poll)

    root.after(100, poll)
    _started.set()
    root.mainloop()
