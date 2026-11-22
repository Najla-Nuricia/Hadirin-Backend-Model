"""Face recognition registration, update, verification, and status routes."""

from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile, status

from app.api.deps import get_current_student, get_face_service
from app.api.helpers import extract_face_samples_from_request
from app.schemas.auth import MessageResponse
from app.schemas.wajah import (
    FaceRegistrationResponse,
    FaceStatusResponse,
    FaceVerifyResponse,
)
from app.services import FaceService

router = APIRouter(prefix="/mahasiswa/wajah", tags=["Registrasi & Verifikasi Wajah"])


@router.get("/status", response_model=FaceStatusResponse)
def get_face_status(
    current_student: dict[str, Any] = Depends(get_current_student),
    face_service: FaceService = Depends(get_face_service),
) -> FaceStatusResponse:
    """Return active face registration count, Storage paths, and configured threshold."""
    return face_service.get_status(str(current_student["nim"]))


@router.post(
    "/register",
    response_model=FaceRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_face(
    request: Request,
    files: list[UploadFile] | None = File(default=None),
    current_student: dict[str, Any] = Depends(get_current_student),
    face_service: FaceService = Depends(get_face_service),
) -> FaceRegistrationResponse:
    """Register initial student face embeddings (multipart images or base64 JSON)."""
    samples = await extract_face_samples_from_request(
        request=request,
        bound_files=files,
        allow_multiple=True,
    )
    return face_service.register_face(str(current_student["nim"]), samples)


@router.put("/update", response_model=FaceRegistrationResponse)
async def update_face(
    request: Request,
    files: list[UploadFile] | None = File(default=None),
    current_student: dict[str, Any] = Depends(get_current_student),
    face_service: FaceService = Depends(get_face_service),
) -> FaceRegistrationResponse:
    """Replace active face samples with newly aligned and encoded MobileFaceNet embeddings."""
    samples = await extract_face_samples_from_request(
        request=request,
        bound_files=files,
        allow_multiple=True,
    )
    return face_service.update_face(str(current_student["nim"]), samples)


@router.post("/verify", response_model=FaceVerifyResponse)
async def verify_face(
    request: Request,
    file: UploadFile | None = File(default=None),
    current_student: dict[str, Any] = Depends(get_current_student),
    face_service: FaceService = Depends(get_face_service),
) -> FaceVerifyResponse:
    """Compare a probe image against the logged-in student's averaged face embedding."""
    samples = await extract_face_samples_from_request(
        request=request,
        bound_single=file,
        allow_multiple=False,
    )
    image_bytes = samples[0][0]
    return face_service.verify_face_bytes(str(current_student["nim"]), image_bytes)


@router.delete("", response_model=MessageResponse)
def delete_face_data(
    current_student: dict[str, Any] = Depends(get_current_student),
    face_service: FaceService = Depends(get_face_service),
) -> MessageResponse:
    """Delete all registered face embeddings and Storage images for the student."""
    return face_service.delete_face(str(current_student["nim"]))

