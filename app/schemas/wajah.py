"""Pydantic schemas for student face registration, update, status, and verification."""

from pydantic import BaseModel, Field


class FaceStatusResponse(BaseModel):
    """Current face registration status for the logged-in student."""

    nim: str
    is_registered: bool
    active_samples: int
    embedding_dimension: int | None = None
    threshold: float
    storage_paths: list[str] = Field(default_factory=list)
    sample_urls: list[str] = Field(default_factory=list)
    last_updated_at: str | None = None


class FaceBase64Payload(BaseModel):
    """JSON payload supporting single or multi-frame base64 face submissions."""

    image_base64: str | None = None
    images_base64: list[str] | None = None


class FaceRegistrationResponse(BaseModel):
    """Result after registering or updating face embeddings and images."""

    message: str
    nim: str
    samples_saved: int
    embedding_dimension: int
    threshold: float
    storage_paths: list[str]
    is_registered: bool = True


class FaceVerifyResponse(BaseModel):
    """Face verification similarity verdict."""

    matched: bool
    status: str
    label: str
    nim: str
    similarity: float
    threshold: float
    active_samples: int

