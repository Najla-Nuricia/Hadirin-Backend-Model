"""Health and readiness probe routes."""

from pathlib import Path

from fastapi import APIRouter, Depends, Response, status
from supabase import Client

from app.api.deps import get_db_client
from app.core.config import Settings, get_settings

router = APIRouter(tags=["Health"])

_WEIGHT_FILENAMES = (
    "MobileFace_Net",
    "pnet_Weights",
    "rnet_Weights",
    "onet_Weights",
)


@router.get("/health")
def health_check(
    response: Response,
    client: Client = Depends(get_db_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Verify Supabase DB connectivity and ML model weight availability."""
    db_status = "connected"
    try:
        client.table("program_studi").select("kode").limit(1).execute()
    except Exception as exc:
        db_status = f"error: {exc.__class__.__name__}"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    weights_dir = Path(settings.ml_weights_dir)
    ml_ready = all((weights_dir / name).is_file() for name in _WEIGHT_FILENAMES)

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "ml_weights_ready": ml_ready,
    }

