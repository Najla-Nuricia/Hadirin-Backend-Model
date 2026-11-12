"""FastAPI dependency providers for settings, repositories, services, and JWT auth."""

from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.repositories import (
    AuthRepository,
    DosenRepository,
    FotoWajahRepository,
    JadwalRepository,
    KehadiranRepository,
    MahasiswaRepository,
    PengajuanRepository,
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

