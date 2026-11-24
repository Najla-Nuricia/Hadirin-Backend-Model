"""Public routes for fetching class and subject data (no auth required for registration)."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from supabase import Client

from app.api.deps import get_db_client

router = APIRouter(prefix="/kelas", tags=["Kelas & Mata Kuliah"])


class KelasItem(BaseModel):
    id: str
    nama: str
    tingkat: int
    program_studi_kode: str
    tahun_ajaran_id: str


class KelasListResponse(BaseModel):
    data: list[KelasItem]
    total: int


class MatkulItem(BaseModel):
    id: str | None = None
    nama: str
    kode: str | None = None


class MatkulListResponse(BaseModel):
    data: list[MatkulItem]
    total: int
    kelas_nama: str | None = None


@router.get("", response_model=KelasListResponse)
def list_kelas(
    tahun_ajaran: str | None = Query(
        default=None,
        description="Filter tahun ajaran ('2026/2027').",
        examples=["2026/2027"],
    ),
    program_studi_kode: str | None = Query(
        default=None,
        description="Filter kode program studi ('D4-TI').",
        examples=["D4-TI"],
    ),
    client: Client = Depends(get_db_client),
) -> KelasListResponse:
    """Return classes with level/prodi/year metadata (public, no auth required)."""
    query = client.table("kelas").select(
        "id,nama,tingkat,program_studi_kode,tahun_ajaran_id"
    )
    if program_studi_kode and program_studi_kode.strip():
        query = query.eq("program_studi_kode", program_studi_kode.strip().upper())
    if tahun_ajaran and tahun_ajaran.strip():
        tahun_res = (
            client.table("tahun_ajaran")
            .select("id")
            .eq("tahun", tahun_ajaran.strip())
            .limit(1)
            .execute()
        )
        if not tahun_res.data:
            return KelasListResponse(data=[], total=0)
        query = query.eq("tahun_ajaran_id", tahun_res.data[0]["id"])

    res = query.order("tingkat").order("nama").execute()
    rows = res.data or []
    items = [
        KelasItem(
            id=str(row["id"]),
            nama=str(row["nama"]),
            tingkat=int(row["tingkat"]),
            program_studi_kode=str(row["program_studi_kode"]),
            tahun_ajaran_id=str(row["tahun_ajaran_id"]),
        )
        for row in rows
    ]
    return KelasListResponse(data=items, total=len(items))


@router.get("/{kelas_id}/matkul", response_model=MatkulListResponse)
def list_matkul_by_kelas(
    kelas_id: str,
    client: Client = Depends(get_db_client),
) -> MatkulListResponse:
    """Return distinct mata kuliah for a given kelas_id from v_jadwal_lengkap."""
    # Get kelas name first
    kelas_res = client.table("kelas").select("nama").eq("id", kelas_id).limit(1).execute()
    kelas_nama: str | None = None
    if kelas_res.data:
        kelas_nama = kelas_res.data[0].get("nama")

    # Get schedules for this class and extract distinct mata kuliah
    jadwal_res = (
        client.table("v_jadwal_lengkap")
        .select("matkul_nama,matkul_kode")
        .eq("kelas_nama", kelas_nama or kelas_id)
        .execute()
    )
    seen: set[str] = set()
    items: list[MatkulItem] = []
    for row in jadwal_res.data or []:
        nama = str(row.get("matkul_nama") or "").strip()
        kode = str(row.get("matkul_kode") or "").strip() or None
        if nama and nama not in seen:
            seen.add(nama)
            items.append(MatkulItem(nama=nama, kode=kode))

    items.sort(key=lambda x: x.nama)
    return MatkulListResponse(data=items, total=len(items), kelas_nama=kelas_nama)

