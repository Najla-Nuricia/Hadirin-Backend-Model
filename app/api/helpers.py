"""Shared FastAPI request parsing helpers for dual JSON/multipart upload endpoints."""

from typing import Any

from fastapi import Request, UploadFile
from pydantic import ValidationError
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.core.exceptions import BadRequestError
from app.schemas.wajah import FaceBase64Payload
from app.services.face_recognition.face_service import FaceService


async def parse_json_body(request: Request) -> dict[str, Any]:
    """Safely decode a JSON object body."""
    try:
        data = await request.json()
    except Exception as exc:
        raise BadRequestError("Body JSON tidak valid.") from exc
    if not isinstance(data, dict):
        raise BadRequestError("Body JSON harus berupa objek.")
    return data


async def collect_uploaded_files(
    request: Request,
    bound_files: list[UploadFile] | None = None,
    bound_single: UploadFile | None = None,
) -> list[UploadFile]:
    """Collect UploadFile objects bound by FastAPI or present in the raw multipart form."""
    collected: list[UploadFile] = []
    if bound_single is not None:
        collected.append(bound_single)
    if bound_files:
        collected.extend(bound_files)
    if collected:
        return collected

    form = await request.form()
    for _, value in form.multi_items():
        if isinstance(value, (UploadFile, StarletteUploadFile)):
            collected.append(value)  # type: ignore[arg-type]
    return collected


async def extract_face_samples_from_request(
    request: Request,
    bound_files: list[UploadFile] | None = None,
    bound_single: UploadFile | None = None,
    allow_multiple: bool = True,
) -> list[tuple[bytes, str, str]]:
    """Extract `(bytes, filename, content_type)` image samples from multipart or base64 JSON."""
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        raw = await parse_json_body(request)
        try:
            payload = FaceBase64Payload.model_validate(raw)
        except ValidationError as exc:
            raise BadRequestError(f"Format JSON gambar wajah tidak valid: {exc.errors()[0]['msg']}") from exc

        b64_items: list[str] = []
        if payload.images_base64:
            b64_items.extend(payload.images_base64)
        if payload.image_base64:
            b64_items.append(payload.image_base64)

        if not b64_items:
            raise BadRequestError("Sertakan `images_base64` atau `image_base64` pada body JSON.")
        if not allow_multiple and len(b64_items) > 1:
            b64_items = b64_items[:1]

        return [
            FaceService.decode_base64_sample(item, index=idx)
            for idx, item in enumerate(b64_items, start=1)
        ]

    uploads = await collect_uploaded_files(
        request=request,
        bound_files=bound_files,
        bound_single=bound_single,
    )
    if not uploads:
        raise BadRequestError("Unggah minimal satu file foto wajah pada form multipart.")
    if not allow_multiple and len(uploads) > 1:
        uploads = uploads[:1]

    samples: list[tuple[bytes, str, str]] = []
    for upload in uploads:
        data = await upload.read()
        samples.append(
            (
                data,
                upload.filename or "face.jpg",
                upload.content_type or "image/jpeg",
            )
        )
    return samples

