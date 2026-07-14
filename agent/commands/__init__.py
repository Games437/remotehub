from agent.commands import media_web, screenshot, system, telemetry

DISPATCH = {
    "lock": lambda payload: system.lock(),
    "shutdown": lambda payload: system.shutdown(payload),
    "restart": lambda payload: system.restart(payload),
    "cancel_shutdown": lambda payload: system.cancel_shutdown(),
    "sleep": lambda payload: system.sleep(),
    "screenshot": lambda payload: screenshot.capture(),
    "open_website": media_web.open_website,
    "open_program": media_web.open_program,
    "play_music": media_web.play_music,
    "notification": media_web.notify,
    "clipboard": media_web.clipboard,
    "get_idle_time": lambda payload: telemetry.get_idle_time(),
    "list_processes": lambda payload: telemetry.list_processes(),
    "get_active_window": lambda payload: telemetry.get_active_window(),
    "list_open_windows": lambda payload: telemetry.list_open_windows(),
    "get_network_status": lambda payload: telemetry.get_network_status(),
}
