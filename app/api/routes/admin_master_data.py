"""Admin-only CRUD routes for academic master data."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_admin_master_data_service,
    get_admin_options_service,
    get_current_admin,
)
from app.schemas.admin_master_data import (
    AdminDosenListResponse,
    AdminMataKuliahItem,
    AdminMataKuliahListResponse,
    AdminMataKuliahMutationResponse,
    AdminMataKuliahWriteRequest,
    AdminProgramStudiListResponse,
    AdminRuanganItem,
    AdminRuanganListResponse,
    AdminRuanganQrItem,
    AdminRuanganQrListResponse,
    AdminSesiKuliahListResponse,
    AdminTahunAjaranItem,
    AdminTahunAjaranListResponse,
    AdminTahunAjaranMutationResponse,
    AdminTahunAjaranWriteRequest,
)
from app.schemas.auth import MessageResponse
from app.services.admin_master_data_service import AdminMasterDataService
from app.services.admin_options_service import AdminOptionsService


router = APIRouter(prefix="/admin", tags=["Admin Master Data"])


@router.get("/tahun-ajaran", response_model=AdminTahunAjaranListResponse)
def list_tahun_ajaran(
    search: str | None = Query(default=None, max_length=20),
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminTahunAjaranListResponse:
    return service.list_tahun_ajaran(search)


@router.get("/tahun-ajaran/{item_id}", response_model=AdminTahunAjaranItem)
def get_tahun_ajaran(
    item_id: UUID,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminTahunAjaranItem:
    return service.get_tahun_ajaran(str(item_id))


@router.post(
    "/tahun-ajaran",
    response_model=AdminTahunAjaranMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tahun_ajaran(
    payload: AdminTahunAjaranWriteRequest,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminTahunAjaranMutationResponse:
    return service.create_tahun_ajaran(payload)


@router.put("/tahun-ajaran/{item_id}", response_model=AdminTahunAjaranMutationResponse)
def update_tahun_ajaran(
    item_id: UUID,
    payload: AdminTahunAjaranWriteRequest,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminTahunAjaranMutationResponse:
    return service.update_tahun_ajaran(str(item_id), payload)


@router.delete("/tahun-ajaran/{item_id}", response_model=MessageResponse)
def delete_tahun_ajaran(
    item_id: UUID,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> MessageResponse:
    return service.delete_tahun_ajaran(str(item_id))


@router.get("/mata-kuliah", response_model=AdminMataKuliahListResponse)
def list_mata_kuliah(
    search: str | None = Query(default=None, max_length=100),
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminMataKuliahListResponse:
    return service.list_mata_kuliah(search)


@router.get("/mata-kuliah/{kode}", response_model=AdminMataKuliahItem)
def get_mata_kuliah(
    kode: str,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminMataKuliahItem:
    return service.get_mata_kuliah(kode)


@router.post(
    "/mata-kuliah",
    response_model=AdminMataKuliahMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_mata_kuliah(
    payload: AdminMataKuliahWriteRequest,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminMataKuliahMutationResponse:
    return service.create_mata_kuliah(payload)


@router.put("/mata-kuliah/{kode}", response_model=AdminMataKuliahMutationResponse)
def update_mata_kuliah(
    kode: str,
    payload: AdminMataKuliahWriteRequest,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminMataKuliahMutationResponse:
    return service.update_mata_kuliah(kode, payload)


@router.delete("/mata-kuliah/{kode}", response_model=MessageResponse)
def delete_mata_kuliah(
    kode: str,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> MessageResponse:
    return service.delete_mata_kuliah(kode)


@router.get(
    "/dosen",
    response_model=AdminDosenListResponse,
    summary="Daftar dosen untuk pilihan jadwal (admin)",
    description="Mengambil seluruh dosen (termasuk Dosen Testing) untuk dropdown dosen pengampu.",
)
def list_admin_dosen(
    search: str | None = Query(default=None, max_length=100),
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminOptionsService = Depends(get_admin_options_service),
) -> AdminDosenListResponse:
    return service.list_dosen(search)


@router.get(
    "/program-studi",
    response_model=AdminProgramStudiListResponse,
    summary="Daftar program studi (admin)",
)
def list_admin_program_studi(
    search: str | None = Query(default=None, max_length=100),
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminOptionsService = Depends(get_admin_options_service),
) -> AdminProgramStudiListResponse:
    return service.list_program_studi(search)


@router.get(
    "/ruangan",
    response_model=AdminRuanganListResponse,
    summary="Daftar ruangan (admin)",
)
def list_admin_ruangan(
    search: str | None = Query(default=None, max_length=100),
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminOptionsService = Depends(get_admin_options_service),
) -> AdminRuanganListResponse:
    return service.list_ruangan(search)


@router.get(
    "/ruangan/qr-statis",
    response_model=AdminRuanganQrListResponse,
    summary="Daftar kartu QR statis pintu ruangan (admin)",
    description=(
        "Mengembalikan data kartu QR statis seluruh ruangan untuk dicetak/ditempel di pintu kelas. "
        "Format token bersifat deterministik: HADIRIN:ROOM:<kode>."
    ),
)
def list_admin_ruangan_qr(
    search: str | None = Query(default=None, max_length=100),
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminOptionsService = Depends(get_admin_options_service),
) -> AdminRuanganQrListResponse:
    return service.list_ruangan_qr(search)


@router.get(
    "/ruangan/{kode}/qr-statis",
    response_model=AdminRuanganQrItem,
    summary="Kartu QR statis pintu satu ruangan (admin)",
    description="Mengembalikan kartu QR statis siap cetak untuk satu ruangan berdasarkan kode.",
)
def get_admin_ruangan_qr(
    kode: str,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminOptionsService = Depends(get_admin_options_service),
) -> AdminRuanganQrItem:
    return service.get_ruangan_qr(kode)


@router.get(
    "/sesi-kuliah",
    response_model=AdminSesiKuliahListResponse,
    summary="Daftar sesi kuliah (admin)",
)
def list_admin_sesi_kuliah(
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminOptionsService = Depends(get_admin_options_service),
) -> AdminSesiKuliahListResponse:
    return service.list_sesi_kuliah()
