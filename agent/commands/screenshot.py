"""
Screenshot capture.

NOTE: returning the full image as base64 inside the websocket ack (as done
here for simplicity) is fine for occasional low-res captures but will bloat
the `commands` table and the socket message for anything larger. For real
usage, have the agent PUT the PNG directly to object storage (S3/R2) using
a short-lived pre-signed URL issued by the server, and send back just that
URL in the ack.
"""
import base64
import io


def capture() -> dict:
    try:
        import pyautogui
    except ImportError:
        return {"ok": False, "error": "pyautogui is not installed on this agent"}

    image = pyautogui.screenshot()
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return {"ok": True, "image_base64": encoded, "format": "png"}
