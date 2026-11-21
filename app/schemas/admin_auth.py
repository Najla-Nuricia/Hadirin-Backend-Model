"""Pydantic schemas for local admin authentication (JWT)."""

from pydantic import BaseModel, Field, field_validator


class AdminLoginRequest(BaseModel):
    """Credentials for admin sign-in. Values come from environment configuration."""

    username: str = Field(
        ...,
        min_length=1,
        max_length=150,
        json_schema_extra={"example": "adminhadirin"},
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        json_schema_extra={"example": "admin123"},
    )

    @field_validator("username")
    @classmethod
    def _strip_username(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Username admin wajib diisi.")
        return cleaned


class AdminProfileResponse(BaseModel):
    """Authenticated admin snapshot returned on login and `/auth/admin/me`."""

    username: str = Field(..., json_schema_extra={"example": "adminhadirin"})
    name: str = Field(default="Administrator", json_schema_extra={"example": "Administrator"})
    role: str = Field(default="Admin", json_schema_extra={"example": "Admin"})


class AdminLoginResponse(AdminProfileResponse):
    """Admin login response issuing an HS256 JWT with `role=admin`."""

    token: str = Field(..., description="JWT yang sama dengan access_token (kompatibilitas klien).")
    access_token: str = Field(..., description="Bearer token untuk endpoint admin.")
    token_type: str = Field(default="bearer", json_schema_extra={"example": "bearer"})
    expires_in: int = Field(..., description="Masa berlaku token dalam detik.", json_schema_extra={"example": 86400})
