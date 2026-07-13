import secrets
from datetime import datetime, timedelta, timezone

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import (
    Confirm2FARequest,
    Enable2FAResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordConfirm,
    ResetPasswordRequest,
    TokenPair,
    UserOut,
    VerifyEmailRequest,
)
from app.services.audit import log_event
from app.services.email import send_password_reset_email, send_verification_email

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        email_verify_token=secrets.token_urlsafe(32),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    send_verification_email(user.email, user.email_verify_token)
    log_event(db, user_id=str(user.id), action="register", ip_address=_client_ip(request))
    return user


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
def verify_email(body: VerifyEmailRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email_verify_token == body.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    user.is_verified = True
    user.email_verify_token = None
    db.commit()


@router.post("/login", response_model=TokenPair)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    ip = _client_ip(request)

    if not user or not verify_password(body.password, user.hashed_password):
        log_event(db, user_id=None, action="login", ip_address=ip, result="failure", detail={"email": body.email})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    if user.totp_enabled:
        if not body.totp_code or not pyotp.TOTP(user.totp_secret).verify(body.totp_code, valid_window=1):
            log_event(db, user_id=str(user.id), action="login_2fa", ip_address=ip, result="failure")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing 2FA code")

    log_event(db, user_id=str(user.id), action="login", ip_address=ip)
    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("wrong token type")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = payload["sub"]
    # NOTE: for full revocation support, keep a denylist/allowlist of `jti`
    # values (e.g. in Redis) and check it here so refresh tokens can be
    # invalidated server-side on logout / password change.
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/request-password-reset", status_code=status.HTTP_204_NO_CONTENT)
def request_password_reset(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if user:
        user.password_reset_token = secrets.token_urlsafe(32)
        user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        db.commit()
        send_password_reset_email(user.email, user.password_reset_token)
    # Always 204, regardless of whether the email exists — avoids leaking
    # which addresses are registered.


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(body: ResetPasswordConfirm, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.password_reset_token == body.token).first()
    if not user or not user.password_reset_expires or user.password_reset_expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.hashed_password = hash_password(body.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    db.commit()
    log_event(db, user_id=str(user.id), action="password_reset")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/2fa/enable", response_model=Enable2FAResponse)
def enable_2fa(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    secret = pyotp.random_base32()
    user.totp_secret = secret
    db.commit()
    otpauth_url = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="RemoteHub")
    return Enable2FAResponse(secret=secret, otpauth_url=otpauth_url)


@router.post("/2fa/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_2fa(body: Confirm2FARequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.totp_secret or not pyotp.TOTP(user.totp_secret).verify(body.totp_code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid 2FA code")
    user.totp_enabled = True
    db.commit()
    log_event(db, user_id=str(user.id), action="2fa_enabled")


@router.post("/2fa/disable", status_code=status.HTTP_204_NO_CONTENT)
def disable_2fa(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.totp_enabled = False
    user.totp_secret = None
    db.commit()
    log_event(db, user_id=str(user.id), action="2fa_disabled")
