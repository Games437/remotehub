import hmac
import hashlib
import time


def sign_challenge(machine_uid: str, secret: str, nonce: str) -> str:
    msg = f"{machine_uid}:{nonce}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def sign_chat_reply(secret: str, message: str, timestamp: int, nonce: str) -> str:
    """Same HMAC scheme as sign_challenge, just over a chat reply instead
    of the login handshake — see backend core/security.verify_chat_reply."""
    msg = f"{message}:{timestamp}:{nonce}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def verify_command(secret: str, command_type: str, timestamp: int, nonce: str, signature: str, max_skew: int = 30):
    """
    The agent independently re-derives the expected signature before
    running any command. Even though the transport is already TLS, this
    stops a compromised or buggy server component from replaying an old
    command or a malformed one from being executed silently.
    """
    now = int(time.time())
    if abs(now - timestamp) > max_skew:
        return False, "stale timestamp"

    msg = f"{command_type}:{timestamp}:{nonce}".encode()
    expected = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False, "signature mismatch"
    return True, ""
