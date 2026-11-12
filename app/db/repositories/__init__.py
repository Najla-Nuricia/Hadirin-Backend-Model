"""Database repository classes."""

from app.db.repositories.auth_repository import AuthRepository
from app.db.repositories.base import BaseRepository
from app.db.repositories.dosen_repository import DosenRepository
from app.db.repositories.foto_wajah_repository import FotoWajahRepository
from app.db.repositories.jadwal_repository import JadwalRepository
from app.db.repositories.kehadiran_repository import KehadiranRepository
from app.db.repositories.mahasiswa_repository import MahasiswaRepository
from app.db.repositories.pengajuan_repository import PengajuanRepository

__all__ = [
    "AuthRepository",
    "BaseRepository",
    "DosenRepository",
    "FotoWajahRepository",
    "JadwalRepository",
    "KehadiranRepository",
    "MahasiswaRepository",
    "PengajuanRepository",
]

