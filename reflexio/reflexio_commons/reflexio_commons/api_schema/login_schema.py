from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    api_key: str
    token_type: str
    feature_flags: Optional[dict[str, bool]] = None
    auto_verified: Optional[bool] = None


class User(BaseModel):
    email: str


# Email verification models
class VerifyEmailRequest(BaseModel):
    token: str


class VerifyEmailResponse(BaseModel):
    success: bool
    message: str


class ResendVerificationRequest(BaseModel):
    email: str


class ResendVerificationResponse(BaseModel):
    success: bool
    message: str


# Password reset models
class ForgotPasswordRequest(BaseModel):
    email: str


class ForgotPasswordResponse(BaseModel):
    success: bool
    message: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ResetPasswordResponse(BaseModel):
    success: bool
    message: str
