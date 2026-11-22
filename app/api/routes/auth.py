"""Authentication, registration, password change, and current user routes."""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    get_admin_auth_service,
    get_auth_service,
    get_current_admin,
    get_current_student,
    get_mahasiswa_repository,
    get_mahasiswa_service,
)
from app.db.repositories import MahasiswaRepository
from app.schemas.admin_auth import (
    AdminChangeEmailRequest,
    AdminChangePasswordRequest,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminProfileResponse,
)
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
from app.services.admin_auth_service import AdminAuthService

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


@router.post(
    "/auth/admin/login",
    response_model=AdminLoginResponse,
    tags=["Admin Authentication"],
    summary="Login admin",
    description=(
        "Autentikasi admin Hadirin. Kredensial diverifikasi ke **Supabase Auth** "
        "(email dari `ADMIN_EMAIL`, identifier `ADMIN_USERNAME` juga diterima), "
        "lalu user harus terhubung ke tabel `admin`. Response berisi JWT HS256 `role=admin`.\n\n"
        "Contoh request body:\n"
        '```json\n{"username": "adminhadirin", "password": "admin123"}\n```'
    ),
    responses={
        200: {
            "description": "Login admin berhasil.",
            "content": {
                "application/json": {
                    "example": {
                        "username": "adminhadirin",
                        "name": "Administrator",
                        "role": "Admin",
                        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbmhhZGlyaW4iLCJyb2xlIjoiYWRtaW4ifQ.signature",
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbmhhZGlyaW4iLCJyb2xlIjoiYWRtaW4ifQ.signature",
                        "token_type": "bearer",
                        "expires_in": 86400,
                    }
                }
            },
        },
        401: {
            "description": "Username atau password admin salah.",
            "content": {
                "application/json": {
                    "example": {"detail": "Username atau password admin salah.", "code": "unauthorized"}
                }
            },
        },
    },
)
def login_admin(
    payload: AdminLoginRequest,
    admin_service: AdminAuthService = Depends(get_admin_auth_service),
) -> AdminLoginResponse:
    """Authenticate local admin credentials and issue an admin-scoped Bearer JWT."""
    return admin_service.login(payload)


@router.get(
    "/auth/admin/me",
    response_model=AdminProfileResponse,
    tags=["Admin Authentication"],
    summary="Profil admin (terlindungi JWT)",
    description=(
        "Endpoint contoh yang dilindungi `get_current_admin`. Semua endpoint admin "
        "wajib memakai dependency yang sama.\n\n"
        "Contoh header: `Authorization: Bearer <access_token>`\n\n"
        'Contoh response:\n```json\n{"username": "adminhadirin", "name": "Administrator", "role": "Admin"}\n```'
    ),
    responses={
        200: {
            "description": "Identitas admin aktif.",
            "content": {
                "application/json": {
                    "example": {
                        "username": "adminhadirin",
                        "name": "Administrator",
                        "role": "Admin",
                    }
                }
            },
        },
        401: {
            "description": "Header Bearer tidak ada atau JWT tidak valid.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Header Authorization Bearer wajib disertakan.",
                        "code": "unauthorized",
                    }
                }
            },
        },
        403: {
            "description": "Token bukan token admin.",
            "content": {
                "application/json": {
                    "example": {"detail": "Endpoint ini hanya untuk admin.", "code": "forbidden"}
                }
            },
        },
    },
)
def get_admin_profile(
    current_admin: dict[str, Any] = Depends(get_current_admin),
) -> AdminProfileResponse:
    """Return the authenticated admin identity from a validated JWT."""
    return AdminProfileResponse(**current_admin)


@router.put(
    "/auth/admin/change-password",
    response_model=MessageResponse,
    tags=["Admin Authentication"],
    summary="Ubah password admin",
    description=(
        "Mengubah password admin di **Supabase Auth** setelah memverifikasi password saat ini. "
        "Wajib menggunakan Bearer token admin.\n\n"
        'Contoh request body:\n```json\n{"current_password": "admin123", "new_password": "rahasia456", "confirm_password": "rahasia456"}\n```'
    ),
    responses={
        200: {
            "description": "Password admin berhasil diubah.",
            "content": {"application/json": {"example": {"message": "Password admin berhasil diubah."}}},
        },
        400: {"description": "Password saat ini salah / konfirmasi tidak cocok."},
        401: {"description": "Bearer token admin tidak ada atau tidak valid."},
        403: {"description": "Token bukan token admin."},
    },
)
def change_admin_password(
    payload: AdminChangePasswordRequest,
    current_admin: dict[str, Any] = Depends(get_current_admin),
    admin_service: AdminAuthService = Depends(get_admin_auth_service),
) -> MessageResponse:
    """Verify current password and update the authenticated admin's password."""
    return admin_service.change_password(current_admin, payload)


@router.put(
    "/auth/admin/change-email",
    response_model=MessageResponse,
    tags=["Admin Authentication"],
    summary="Ubah email admin",
    description=(
        "Mengubah email admin di **Supabase Auth** dan tabel `admin` setelah memverifikasi "
        "password saat ini. Email baru tidak boleh digunakan akun lain. Login dengan "
        "`ADMIN_USERNAME` tetap memakai email terbaru.\n\n"
        'Contoh request body:\n```json\n{"new_email": "admin.baru@hadirin.polinema.ac.id", "current_password": "admin123"}\n```'
    ),
    responses={
        200: {
            "description": "Email admin berhasil diubah.",
            "content": {"application/json": {"example": {"message": "Email admin berhasil diubah."}}},
        },
        400: {"description": "Password salah atau email baru sama dengan email lama."},
        401: {"description": "Bearer token admin tidak ada atau tidak valid."},
        403: {"description": "Token bukan token admin."},
        409: {"description": "Email sudah digunakan akun lain."},
    },
)
def change_admin_email(
    payload: AdminChangeEmailRequest,
    current_admin: dict[str, Any] = Depends(get_current_admin),
    admin_service: AdminAuthService = Depends(get_admin_auth_service),
) -> MessageResponse:
    """Verify current password and update the authenticated admin's email."""
    return admin_service.change_email(current_admin, payload)

