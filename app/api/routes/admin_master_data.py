"""Admin-only CRUD routes for academic master data."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_admin_master_data_service, get_current_admin
from app.schemas.admin_master_data import (
    AdminMataKuliahItem,
    AdminMataKuliahListResponse,
    AdminMataKuliahMutationResponse,
    AdminMataKuliahWriteRequest,
    AdminTahunAjaranItem,
    AdminTahunAjaranListResponse,
    AdminTahunAjaranMutationResponse,
    AdminTahunAjaranWriteRequest,
)
from app.schemas.auth import MessageResponse
from app.services.admin_master_data_service import AdminMasterDataService


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
