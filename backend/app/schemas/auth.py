import uuid

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None  # required only if the account has 2FA enabled


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
    totp_code: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    is_verified: bool
    totp_enabled: bool

    class Config:
        from_attributes = True
