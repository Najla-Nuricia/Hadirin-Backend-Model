"""Public routes for fetching class and subject data (no auth required for registration)."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from supabase import Client

from app.api.deps import get_db_client

router = APIRouter(prefix="/kelas", tags=["Kelas & Mata Kuliah"])


class KelasItem(BaseModel):
    id: str
    nama: str


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
    client: Client = Depends(get_db_client),
) -> KelasListResponse:
    """Return all available class names from the `kelas` table (public, no auth required)."""
    res = client.table("kelas").select("id,nama").order("nama").execute()
    rows = res.data or []
    items = [KelasItem(id=str(r["id"]), nama=str(r["nama"])) for r in rows]
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

