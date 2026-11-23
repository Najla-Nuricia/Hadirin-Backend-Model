"""Admin-only CRUD routes for the student NIM whitelist."""

from typing import Any

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_admin, get_whitelist_nim_service
from app.schemas.auth import MessageResponse
from app.schemas.whitelist_nim import (
    WhitelistNimListResponse,
    WhitelistNimMutationResponse,
    WhitelistNimWriteRequest,
)
from app.services.whitelist_nim_service import WhitelistNimService


router = APIRouter(prefix="/admin", tags=["Admin Whitelist NIM"])


@router.get("/whitelist-nim", response_model=WhitelistNimListResponse)
def list_whitelist_nim(
    search: str | None = Query(default=None, max_length=100),
    _: dict[str, Any] = Depends(get_current_admin),
    service: WhitelistNimService = Depends(get_whitelist_nim_service),
) -> WhitelistNimListResponse:
    return service.list(search=search)


@router.post(
    "/whitelist-nim",
    response_model=WhitelistNimMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_whitelist_nim(
    payload: WhitelistNimWriteRequest,
    _: dict[str, Any] = Depends(get_current_admin),
    service: WhitelistNimService = Depends(get_whitelist_nim_service),
) -> WhitelistNimMutationResponse:
    return service.create(payload)


@router.put("/whitelist-nim/{nim}", response_model=WhitelistNimMutationResponse)
def update_whitelist_nim(
    nim: str,
    payload: WhitelistNimWriteRequest,
    _: dict[str, Any] = Depends(get_current_admin),
    service: WhitelistNimService = Depends(get_whitelist_nim_service),
) -> WhitelistNimMutationResponse:
    return service.update(nim, payload)


@router.delete("/whitelist-nim/{nim}", response_model=MessageResponse)
def delete_whitelist_nim(
    nim: str,
    _: dict[str, Any] = Depends(get_current_admin),
    service: WhitelistNimService = Depends(get_whitelist_nim_service),
) -> MessageResponse:
    return service.delete(nim)
