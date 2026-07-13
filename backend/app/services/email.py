"""
Stub email sender. Swap the body of `send_email` for a real provider
(SES, Postmark, SendGrid, ...) — kept as a log line here so the rest of the
auth flow (verification, password reset) can be developed and tested
without needing real SMTP credentials.
"""
import logging

logger = logging.getLogger("remotehub.email")


def send_email(to: str, subject: str, body: str) -> None:
    logger.info("EMAIL -> %s | %s\n%s", to, subject, body)


def send_verification_email(to: str, token: str) -> None:
    send_email(
        to,
        "Verify your RemoteHub account",
        f"Click to verify: https://app.example.com/verify-email?token={token}",
    )


def send_password_reset_email(to: str, token: str) -> None:
    send_email(
        to,
        "Reset your RemoteHub password",
        f"Click to reset: https://app.example.com/reset-password?token={token}",
    )
