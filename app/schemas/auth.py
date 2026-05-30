import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    nickname: str | None = None
    grade: Literal["junior_high", "senior_high", "college"] | None = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("密码长度不能少于8位")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    id: uuid.UUID
    email: str
    nickname: str | None
    grade: str | None
    subjects: list[str]
    plan_type: str
    plan_expires_at: datetime | None
    created_at: datetime
    learning_profile: dict | None = None
    voice_enabled: bool = False

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    nickname: str | None = None
    grade: Literal["junior_high", "senior_high", "college"] | None = None
    subjects: list[str] | None = None
