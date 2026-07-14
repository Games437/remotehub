import uuid

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    # Required once the account has 2FA enabled (which, going forward, is
    # every account — see LoginResponse.requires_2fa_setup for accounts
    # that haven't finished enrollment yet).
    totp_code: str | None = Field(default=None, pattern=r"^\d{6}$")


class LoginResponse(BaseModel):
    """
    Two shapes in one model, discriminated by `requires_2fa_setup`:
      - True  -> account has no 2FA yet; `secret`/`otpauth_url` are for the
                 user to scan right now, `setup_token` is a short-lived
                 credential for POST /auth/2fa/setup-confirm. No access/
                 refresh tokens are issued at this point.
      - False -> normal login; access_token/refresh_token are populated.
    """
    requires_2fa_setup: bool = False
    setup_token: str | None = None
    secret: str | None = None
    otpauth_url: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


class Enable2FAResponse(BaseModel):
    secret: str
    otpauth_url: str


class Confirm2FARequest(BaseModel):
    totp_code: str = Field(pattern=r"^\d{6}$")


class Confirm2FASetupRequest(BaseModel):
    """Used once, right after a login response comes back with
    requires_2fa_setup=True — completes enrollment and returns real tokens."""
    setup_token: str
    totp_code: str = Field(pattern=r"^\d{6}$")


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    is_verified: bool
    totp_enabled: bool

    class Config:
        from_attributes = True
