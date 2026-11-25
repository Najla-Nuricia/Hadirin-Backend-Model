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
    AdminDosenItem,
    AdminDosenListResponse,
    AdminDosenMutationResponse,
    AdminDosenWriteRequest,
    AdminKelasItem,
    AdminKelasListResponse,
    AdminKelasMutationResponse,
    AdminKelasWriteRequest,
    AdminMataKuliahItem,
    AdminMataKuliahListResponse,
    AdminMataKuliahMutationResponse,
    AdminMataKuliahWriteRequest,
    AdminProgramStudiListResponse,
    AdminRuanganItem,
    AdminRuanganListResponse,
    AdminRuanganMutationResponse,
    AdminRuanganWriteRequest,
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
    response_model_exclude_none=True,
    summary="Daftar dosen (admin)",
    description="Mengambil seluruh dosen (termasuk Dosen Testing) untuk dropdown dosen pengampu.",
)
def list_admin_dosen(
    search: str | None = Query(default=None, max_length=100),
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminDosenListResponse:
    return service.list_dosen(search)


@router.get("/dosen/{nip}", response_model=AdminDosenItem, response_model_exclude_none=True)
def get_admin_dosen(
    nip: str,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminDosenItem:
    return service.get_dosen(nip)


@router.post(
    "/dosen",
    response_model=AdminDosenMutationResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Buat akun dosen (admin)",
    description=(
        "Membuat akun Supabase Auth dosen dengan password awal dari konfigurasi "
        "`DOSEN_INITIAL_PASSWORD` (default `dosen123`), lalu menyimpan data dosen."
    ),
)
def create_admin_dosen(
    payload: AdminDosenWriteRequest,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminDosenMutationResponse:
    return service.create_dosen(payload)


@router.put("/dosen/{nip}", response_model=AdminDosenMutationResponse, response_model_exclude_none=True)
def update_admin_dosen(
    nip: str,
    payload: AdminDosenWriteRequest,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminDosenMutationResponse:
    return service.update_dosen(nip, payload)


@router.delete("/dosen/{nip}", response_model=MessageResponse)
def delete_admin_dosen(
    nip: str,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> MessageResponse:
    return service.delete_dosen(nip)


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
    response_model_exclude_none=True,
    summary="Daftar ruangan (admin)",
)
def list_admin_ruangan(
    search: str | None = Query(default=None, max_length=100),
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminRuanganListResponse:
    return service.list_ruangan(search)


@router.get("/ruangan/{kode}", response_model=AdminRuanganItem, response_model_exclude_none=True)
def get_admin_ruangan(
    kode: str,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminRuanganItem:
    return service.get_ruangan(kode)


@router.post(
    "/ruangan",
    response_model=AdminRuanganMutationResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_ruangan(
    payload: AdminRuanganWriteRequest,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminRuanganMutationResponse:
    return service.create_ruangan(payload)


@router.put("/ruangan/{kode}", response_model=AdminRuanganMutationResponse, response_model_exclude_none=True)
def update_admin_ruangan(
    kode: str,
    payload: AdminRuanganWriteRequest,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminRuanganMutationResponse:
    return service.update_ruangan(kode, payload)


@router.delete("/ruangan/{kode}", response_model=MessageResponse)
def delete_admin_ruangan(
    kode: str,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> MessageResponse:
    return service.delete_ruangan(kode)


@router.get("/kelas", response_model=AdminKelasListResponse, response_model_exclude_none=True)
def list_admin_kelas(
    search: str | None = Query(default=None, max_length=20),
    program_studi_kode: str | None = Query(default=None, max_length=20),
    tahun_ajaran_id: UUID | None = Query(default=None),
    status_kelas: str | None = Query(default=None, alias="status", max_length=20),
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminKelasListResponse:
    return service.list_kelas(
        search=search,
        program_studi_kode=program_studi_kode,
        tahun_ajaran_id=str(tahun_ajaran_id) if tahun_ajaran_id else None,
        status=status_kelas,
    )


@router.get("/kelas/{kelas_id}", response_model=AdminKelasItem, response_model_exclude_none=True)
def get_admin_kelas(
    kelas_id: UUID,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminKelasItem:
    return service.get_kelas(str(kelas_id))


@router.post(
    "/kelas",
    response_model=AdminKelasMutationResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_kelas(
    payload: AdminKelasWriteRequest,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminKelasMutationResponse:
    return service.create_kelas(payload)


@router.put("/kelas/{kelas_id}", response_model=AdminKelasMutationResponse, response_model_exclude_none=True)
def update_admin_kelas(
    kelas_id: UUID,
    payload: AdminKelasWriteRequest,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> AdminKelasMutationResponse:
    return service.update_kelas(str(kelas_id), payload)


@router.delete("/kelas/{kelas_id}", response_model=MessageResponse)
def delete_admin_kelas(
    kelas_id: UUID,
    _: dict[str, Any] = Depends(get_current_admin),
    service: AdminMasterDataService = Depends(get_admin_master_data_service),
) -> MessageResponse:
    return service.delete_kelas(str(kelas_id))


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
