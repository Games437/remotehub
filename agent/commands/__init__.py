from agent.commands import media_web, screenshot, system

DISPATCH = {
    "lock": lambda payload: system.lock(),
    "shutdown": lambda payload: system.shutdown(),
    "restart": lambda payload: system.restart(),
    "sleep": lambda payload: system.sleep(),
    "screenshot": lambda payload: screenshot.capture(),
    "open_website": media_web.open_website,
    "open_program": media_web.open_program,
    "play_music": media_web.play_music,
    "notification": media_web.notify,
    "clipboard": media_web.clipboard,
}
