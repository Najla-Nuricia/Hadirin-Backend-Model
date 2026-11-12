"""Authentication, registration, password change, and current user routes."""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    get_auth_service,
    get_current_student,
    get_mahasiswa_repository,
    get_mahasiswa_service,
)
from app.db.repositories import MahasiswaRepository
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserSummary,
)
from app.services import AuthService, MahasiswaService

router = APIRouter(tags=["Authentication"])


@router.get("/auth/check-nim/{nim}")
def check_nim_registered(
    nim: str,
    mahasiswa_repo: MahasiswaRepository = Depends(get_mahasiswa_repository),
) -> dict[str, object]:
    """Check whether a NIM is already registered before continuing registration steps."""
    cleaned = nim.strip()
    return {
        "nim": cleaned,
        "registered": bool(mahasiswa_repo.get_by_nim(cleaned)),
    }


@router.post(
    "/auth/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_student(
    payload: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> RegisterResponse:
    """Register a new student account linked to Supabase Auth."""
    return auth_service.register(payload)


@router.post("/auth/login", response_model=TokenResponse)
def login_student(
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Authenticate student credentials against Supabase Auth and issue a JWT."""
    return auth_service.login(payload)


@router.put("/auth/change-password", response_model=MessageResponse)
@router.post("/auth/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    current_student: dict[str, Any] = Depends(get_current_student),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Verify current password and update the logged-in student's password."""
    return auth_service.change_password(str(current_student["nim"]), payload)


@router.get("/users/me", response_model=UserSummary)
def get_current_user_profile(
    current_student: dict[str, Any] = Depends(get_current_student),
    mahasiswa_service: MahasiswaService = Depends(get_mahasiswa_service),
) -> UserSummary:
    """Return the authenticated student's normalized account profile."""
    profile = mahasiswa_service.get_profile(str(current_student["nim"]))
    return UserSummary(**profile.model_dump())

