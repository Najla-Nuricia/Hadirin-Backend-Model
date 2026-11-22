"""FastAPI dependency providers for settings, repositories, services, and JWT auth."""

from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.repositories import (
    AdminRepository,
    AuthRepository,
    DosenRepository,
    FotoWajahRepository,
    JadwalRepository,
    KehadiranRepository,
    MahasiswaRepository,
    MataKuliahRepository,
    PengajuanRepository,
    TahunAjaranRepository,
)
from app.db.session import get_supabase_client
from app.services import (
    AuthService,
    DosenService,
    FaceService,
    JadwalService,
    MahasiswaService,
    PengajuanService,
    PresensiService,
)
from app.services.admin_auth_service import AdminAuthService
from app.services.admin_jadwal_service import AdminJadwalService
from app.services.admin_master_data_service import AdminMasterDataService

_bearer_scheme = HTTPBearer(auto_error=False)


def get_db_client(settings: Settings = Depends(get_settings)) -> Client:
    """Provide cached Supabase service-role client."""
    return get_supabase_client(settings)


def get_auth_repository(
    client: Client = Depends(get_db_client),
    settings: Settings = Depends(get_settings),
) -> AuthRepository:
    return AuthRepository(client=client, settings=settings)


def get_mahasiswa_repository(
    client: Client = Depends(get_db_client),
    settings: Settings = Depends(get_settings),
) -> MahasiswaRepository:
    return MahasiswaRepository(client=client, settings=settings)


def get_jadwal_repository(
    client: Client = Depends(get_db_client),
    settings: Settings = Depends(get_settings),
) -> JadwalRepository:
    return JadwalRepository(client=client, settings=settings)


def get_kehadiran_repository(
    client: Client = Depends(get_db_client),
    settings: Settings = Depends(get_settings),
) -> KehadiranRepository:
    return KehadiranRepository(client=client, settings=settings)


def get_pengajuan_repository(
    client: Client = Depends(get_db_client),
    settings: Settings = Depends(get_settings),
) -> PengajuanRepository:
    return PengajuanRepository(client=client, settings=settings)


def get_foto_wajah_repository(
    client: Client = Depends(get_db_client),
    settings: Settings = Depends(get_settings),
) -> FotoWajahRepository:
    return FotoWajahRepository(client=client, settings=settings)


def get_dosen_repository(
    client: Client = Depends(get_db_client),
    settings: Settings = Depends(get_settings),
) -> DosenRepository:
    return DosenRepository(client=client, settings=settings)


def get_dosen_service(
    dosen_repo: DosenRepository = Depends(get_dosen_repository),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    settings: Settings = Depends(get_settings),
) -> DosenService:
    return DosenService(
        dosen_repo=dosen_repo,
        auth_repo=auth_repo,
        settings=settings,
    )


def get_auth_service(
    auth_repo: AuthRepository = Depends(get_auth_repository),
    mahasiswa_repo: MahasiswaRepository = Depends(get_mahasiswa_repository),
    foto_wajah_repo: FotoWajahRepository = Depends(get_foto_wajah_repository),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(
        auth_repo=auth_repo,
        mahasiswa_repo=mahasiswa_repo,
        foto_wajah_repo=foto_wajah_repo,
        settings=settings,
    )


def get_admin_repository(
    client: Client = Depends(get_db_client),
) -> AdminRepository:
    return AdminRepository(client=client)


def get_admin_auth_service(
    auth_repo: AuthRepository = Depends(get_auth_repository),
    admin_repo: AdminRepository = Depends(get_admin_repository),
    settings: Settings = Depends(get_settings),
) -> AdminAuthService:
    return AdminAuthService(auth_repo=auth_repo, admin_repo=admin_repo, settings=settings)


def get_mahasiswa_service(
    mahasiswa_repo: MahasiswaRepository = Depends(get_mahasiswa_repository),
    foto_wajah_repo: FotoWajahRepository = Depends(get_foto_wajah_repository),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    settings: Settings = Depends(get_settings),
) -> MahasiswaService:
    return MahasiswaService(
        mahasiswa_repo=mahasiswa_repo,
        foto_wajah_repo=foto_wajah_repo,
        auth_repo=auth_repo,
        settings=settings,
    )


def get_jadwal_service(
    mahasiswa_repo: MahasiswaRepository = Depends(get_mahasiswa_repository),
    jadwal_repo: JadwalRepository = Depends(get_jadwal_repository),
    kehadiran_repo: KehadiranRepository = Depends(get_kehadiran_repository),
) -> JadwalService:
    return JadwalService(
        mahasiswa_repo=mahasiswa_repo,
        jadwal_repo=jadwal_repo,
        kehadiran_repo=kehadiran_repo,
    )


def get_admin_jadwal_service(
    jadwal_repo: JadwalRepository = Depends(get_jadwal_repository),
    mahasiswa_repo: MahasiswaRepository = Depends(get_mahasiswa_repository),
    dosen_repo: DosenRepository = Depends(get_dosen_repository),
) -> AdminJadwalService:
    """Provide the admin schedule service with read/write repositories."""
    return AdminJadwalService(
        jadwal_repo=jadwal_repo,
        mahasiswa_repo=mahasiswa_repo,
        dosen_repo=dosen_repo,
    )


def get_tahun_ajaran_repository(
    client: Client = Depends(get_db_client),
    settings: Settings = Depends(get_settings),
) -> TahunAjaranRepository:
    return TahunAjaranRepository(client=client, settings=settings)


def get_mata_kuliah_repository(
    client: Client = Depends(get_db_client),
    settings: Settings = Depends(get_settings),
) -> MataKuliahRepository:
    return MataKuliahRepository(client=client, settings=settings)


def get_admin_master_data_service(
    tahun_ajaran_repo: TahunAjaranRepository = Depends(get_tahun_ajaran_repository),
    mata_kuliah_repo: MataKuliahRepository = Depends(get_mata_kuliah_repository),
) -> AdminMasterDataService:
    return AdminMasterDataService(
        tahun_ajaran_repo=tahun_ajaran_repo,
        mata_kuliah_repo=mata_kuliah_repo,
    )


def get_face_service(
    mahasiswa_repo: MahasiswaRepository = Depends(get_mahasiswa_repository),
    foto_wajah_repo: FotoWajahRepository = Depends(get_foto_wajah_repository),
    settings: Settings = Depends(get_settings),
) -> FaceService:
    return FaceService(
        mahasiswa_repo=mahasiswa_repo,
        foto_wajah_repo=foto_wajah_repo,
        settings=settings,
    )


def get_presensi_service(
    mahasiswa_repo: MahasiswaRepository = Depends(get_mahasiswa_repository),
    jadwal_repo: JadwalRepository = Depends(get_jadwal_repository),
    kehadiran_repo: KehadiranRepository = Depends(get_kehadiran_repository),
    face_service: FaceService = Depends(get_face_service),
    settings: Settings = Depends(get_settings),
) -> PresensiService:
    return PresensiService(
        mahasiswa_repo=mahasiswa_repo,
        jadwal_repo=jadwal_repo,
        kehadiran_repo=kehadiran_repo,
        face_service=face_service,
        settings=settings,
    )


def get_pengajuan_service(
    mahasiswa_repo: MahasiswaRepository = Depends(get_mahasiswa_repository),
    jadwal_repo: JadwalRepository = Depends(get_jadwal_repository),
    kehadiran_repo: KehadiranRepository = Depends(get_kehadiran_repository),
    pengajuan_repo: PengajuanRepository = Depends(get_pengajuan_repository),
) -> PengajuanService:
    return PengajuanService(
        mahasiswa_repo=mahasiswa_repo,
        jadwal_repo=jadwal_repo,
        kehadiran_repo=kehadiran_repo,
        pengajuan_repo=pengajuan_repo,
    )


def get_current_student(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
    mahasiswa_repo: MahasiswaRepository = Depends(get_mahasiswa_repository),
) -> dict[str, Any]:
    """Validate Bearer JWT and return the active student record from Supabase."""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Header Authorization Bearer wajib disertakan.")

    payload = decode_access_token(credentials.credentials, settings=settings)
    if payload.get("role") != "mahasiswa":
        raise UnauthorizedError("Token tidak valid untuk akun mahasiswa.")

    nim = str(payload.get("sub") or "")
    student = mahasiswa_repo.get_by_nim(nim)
    if not student:
        raise UnauthorizedError("Akun mahasiswa tidak ditemukan atau sesi tidak valid.")
    return student


def get_current_dosen(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
    dosen_repo: DosenRepository = Depends(get_dosen_repository),
) -> dict[str, Any]:
    """Validate Bearer JWT and return the active lecturer row from Supabase."""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Header Authorization Bearer wajib disertakan.")

    payload = decode_access_token(credentials.credentials, settings=settings)
    role = payload.get("role")
    if role == "mahasiswa":
        raise ForbiddenError("Endpoint ini hanya untuk dosen.")
    if role != "dosen":
        raise UnauthorizedError("Token tidak valid untuk akun dosen.")

    nip = str(payload.get("sub") or "")
    dosen = dosen_repo.get_by_nip(nip)
    if not dosen:
        raise UnauthorizedError("Akun dosen tidak ditemukan atau sesi tidak valid.")
    return dosen


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Validate a Bearer JWT with the `admin` role and return the admin identity.

    Guard for every admin endpoint: `current_admin: dict = Depends(get_current_admin)`.
    Tokens issued for mahasiswa/dosen are rejected with 403.
    """
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Header Authorization Bearer wajib disertakan.")

    payload = decode_access_token(credentials.credentials, settings=settings)
    if payload.get("role") != "admin":
        raise ForbiddenError("Endpoint ini hanya untuk admin.")
    if str(payload.get("sub") or "") != settings.admin_username:
        raise UnauthorizedError("Token admin tidak valid.")

    return {
        "username": settings.admin_username,
        "name": "Administrator",
        "role": "Admin",
        "auth_user_id": str(payload.get("auth_user_id") or ""),
    }

