"""Student absence permission (`surat izin`/`sakit`) routes and Storage document uploads."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from pydantic import ValidationError

from app.api.deps import get_current_student, get_pengajuan_service
from app.api.helpers import collect_uploaded_files, parse_json_body
from app.core.exceptions import BadRequestError
from app.schemas.auth import MessageResponse
from app.schemas.pengajuan import (
    DocumentUploadResponse,
    PengajuanCreateRequest,
    PengajuanListResponse,
    PengajuanMutationResponse,
    PengajuanUpdateRequest,
)
from app.services import PengajuanService

router = APIRouter(prefix="/mahasiswa/pengajuan", tags=["Pengajuan Surat Izin"])


@router.get("", response_model=PengajuanListResponse)
@router.get("/list", response_model=PengajuanListResponse)
def list_pengajuan(
    current_student: dict[str, Any] = Depends(get_current_student),
    pengajuan_service: PengajuanService = Depends(get_pengajuan_service),
) -> PengajuanListResponse:
    """List all absence requests submitted by the authenticated student."""
    return pengajuan_service.list_pengajuan(str(current_student["nim"]))


@router.post(
    "/dokumen",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_pengajuan_document(
    file: UploadFile = File(...),
    current_student: dict[str, Any] = Depends(get_current_student),
    pengajuan_service: PengajuanService = Depends(get_pengajuan_service),
) -> DocumentUploadResponse:
    """Upload a supporting document (`PDF/JPG/PNG`) to Supabase Storage `dokumen-pengajuan`."""
    content = await file.read()
    return pengajuan_service.upload_document(
        nim=str(current_student["nim"]),
        filename=file.filename,
        content=content,
        content_type=file.content_type,
    )


@router.post(
    "/upload",
    response_model=PengajuanMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_pengajuan_multipart(
    jenis: Literal["izin", "sakit", "kompensasi"] = Form(...),
    alasan: str = Form(..., min_length=3, max_length=500),
    matakuliah: str | None = Form(default=None),
    tanggal: str | None = Form(default=None),
    sesi_presensi_id: str | None = Form(default=None),
    jadwal_id: str | None = Form(default=None),
    file: UploadFile = File(...),
    current_student: dict[str, Any] = Depends(get_current_student),
    pengajuan_service: PengajuanService = Depends(get_pengajuan_service),
) -> PengajuanMutationResponse:
    """Submit an absence permission request with an uploaded document in one multipart request."""
    content = await file.read()
    return pengajuan_service.create_pengajuan(
        nim=str(current_student["nim"]),
        jenis=jenis,
        alasan=alasan,
        matakuliah=matakuliah,
        tanggal=tanggal,
        sesi_presensi_id=sesi_presensi_id,
        jadwal_id=jadwal_id,
        file_bytes=content,
        filename=file.filename,
        content_type=file.content_type,
    )


@router.post(
    "",
    response_model=PengajuanMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pengajuan(
    request: Request,
    file: UploadFile | None = File(default=None),
    current_student: dict[str, Any] = Depends(get_current_student),
    pengajuan_service: PengajuanService = Depends(get_pengajuan_service),
) -> PengajuanMutationResponse:
    """Create an absence permission request from either JSON body or multipart form-data."""
    nim = str(current_student["nim"])
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        raw = await parse_json_body(request)
        try:
            payload = PengajuanCreateRequest.model_validate(raw)
        except ValidationError as exc:
            raise BadRequestError(exc.errors()[0]["msg"]) from exc

        return pengajuan_service.create_pengajuan(
            nim=nim,
            jenis=payload.jenis,
            alasan=payload.alasan,
            matakuliah=payload.matakuliah,
            tanggal=payload.tanggal,
            sesi_presensi_id=payload.sesi_presensi_id,
            jadwal_id=payload.jadwal_id,
            dokumen_path=payload.dokumen_path,
        )

    form = await request.form()
    jenis = str(form.get("jenis") or "").strip()
    alasan = str(form.get("alasan") or "").strip()
    if not jenis or not alasan:
        raise BadRequestError("Field `jenis` dan `alasan` wajib diisi.")

    uploads = await collect_uploaded_files(request=request, bound_single=file)
    chosen_file = uploads[0] if uploads else None
    file_bytes = await chosen_file.read() if chosen_file is not None else None

    return pengajuan_service.create_pengajuan(
        nim=nim,
        jenis=jenis,
        alasan=alasan,
        matakuliah=str(form.get("matakuliah")) if form.get("matakuliah") else None,
        tanggal=str(form.get("tanggal")) if form.get("tanggal") else None,
        sesi_presensi_id=str(form.get("sesi_presensi_id")) if form.get("sesi_presensi_id") else None,
        jadwal_id=str(form.get("jadwal_id")) if form.get("jadwal_id") else None,
        dokumen_path=str(form.get("dokumen_path")) if form.get("dokumen_path") else None,
        file_bytes=file_bytes,
        filename=chosen_file.filename if chosen_file is not None else None,
        content_type=chosen_file.content_type if chosen_file is not None else None,
    )


@router.put("/{pengajuan_id}", response_model=PengajuanMutationResponse)
def update_pengajuan(
    pengajuan_id: str,
    payload: PengajuanUpdateRequest,
    current_student: dict[str, Any] = Depends(get_current_student),
    pengajuan_service: PengajuanService = Depends(get_pengajuan_service),
) -> PengajuanMutationResponse:
    """Update a pending absence permission request belonging to the student."""
    return pengajuan_service.update_pengajuan(
        nim=str(current_student["nim"]),
        pengajuan_id=pengajuan_id,
        payload=payload,
    )


@router.delete("/{pengajuan_id}", response_model=MessageResponse)
def delete_pengajuan(
    pengajuan_id: str,
    current_student: dict[str, Any] = Depends(get_current_student),
    pengajuan_service: PengajuanService = Depends(get_pengajuan_service),
) -> MessageResponse:
    """Delete a pending absence request and clean up any attached Storage file."""
    return pengajuan_service.delete_pengajuan(
        nim=str(current_student["nim"]),
        pengajuan_id=pengajuan_id,
    )

