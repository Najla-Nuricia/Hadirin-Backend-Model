"""Database repository classes."""

from app.db.repositories.admin_repository import AdminRepository
from app.db.repositories.auth_repository import AuthRepository
from app.db.repositories.base import BaseRepository
from app.db.repositories.dosen_repository import DosenRepository
from app.db.repositories.foto_wajah_repository import FotoWajahRepository
from app.db.repositories.jadwal_repository import JadwalRepository
from app.db.repositories.kehadiran_repository import KehadiranRepository
from app.db.repositories.mahasiswa_repository import MahasiswaRepository
from app.db.repositories.mata_kuliah_repository import MataKuliahRepository
from app.db.repositories.pengajuan_repository import PengajuanRepository
from app.db.repositories.program_studi_repository import ProgramStudiRepository
from app.db.repositories.ruangan_repository import RuanganRepository
from app.db.repositories.sesi_kuliah_repository import SesiKuliahRepository
from app.db.repositories.tahun_ajaran_repository import TahunAjaranRepository
from app.db.repositories.whitelist_nim_repository import WhitelistNimRepository

__all__ = [
    "AdminRepository",
    "AuthRepository",
    "BaseRepository",
    "DosenRepository",
    "FotoWajahRepository",
    "JadwalRepository",
    "KehadiranRepository",
    "MahasiswaRepository",
    "MataKuliahRepository",
    "PengajuanRepository",
    "ProgramStudiRepository",
    "RuanganRepository",
    "SesiKuliahRepository",
    "TahunAjaranRepository",
    "WhitelistNimRepository",
]

