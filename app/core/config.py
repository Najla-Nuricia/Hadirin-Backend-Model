"""Application settings loaded from environment variables and `.env`."""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    """Typed runtime configuration for database, auth, storage, GPS, and ML."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Supabase
    supabase_url: str = Field(..., min_length=1)
    supabase_service_key: str = Field(..., min_length=1)
    supabase_page_size: int = Field(default=1000, ge=1)

    # Authentication & JWT
    jwt_secret_key: str = Field(..., min_length=1)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=1440, ge=1)
    auth_email_domain: str = "hadirin.local"
    dosen_default_password: str = ""

    # Campus GPS geofencing & QR session TTL
    geofence_name: str = "Area Kampus"
    campus_latitude: float = Field(
        default=-7.946714,
        validation_alias=AliasChoices("CAMPUS_LATITUDE", "GEOFENCE_LATITUDE"),
    )
    campus_longitude: float = Field(
        default=112.615668,
        validation_alias=AliasChoices("CAMPUS_LONGITUDE", "GEOFENCE_LONGITUDE"),
    )
    max_gps_distance_meters: float = Field(
        default=200.0,
        gt=0,
        validation_alias=AliasChoices("MAX_GPS_DISTANCE_METERS", "GEOFENCE_RADIUS_METERS"),
    )
    geofence_max_accuracy_meters: float = Field(default=100.0, ge=0)
    qr_token_ttl_seconds: int = Field(default=30, ge=5)

    # Face recognition (MTCNN + MobileFaceNet)
    face_similarity_threshold: float = Field(default=0.5, ge=-1.0, le=1.0)
    mtcnn_min_face_size: int = Field(default=20, ge=8)
    face_min_samples_recommended: int = Field(default=3, ge=1)
    face_max_samples_per_request: int = Field(default=10, ge=1, le=20)
    ml_weights_dir: Path = BASE_DIR / "ml" / "models" / "weights"

    # Supabase Storage buckets
    storage_bucket_wajah: str = "foto-wajah"
    storage_bucket_presensi: str = "foto-presensi"
    storage_bucket_pengajuan: str = "dokumen-pengajuan"

    # Testing / Development
    testing_bypass_session: bool = Field(default=False, description="Jika True, bypass is_open dan QR expiry untuk testing absensi.")

    # HTTP / CORS
    cors_allow_origins: str = "*"

    def parsed_cors_origins(self) -> list[str]:
        """Return configured CORS origin entries."""
        raw = (self.cors_allow_origins or "").strip()
        if not raw or raw == "*":
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]

    def synthetic_email_for_nim(self, nim: str) -> str:
        """Build deterministic email address for Supabase Auth from a student's NIM."""
        cleaned_nim = nim.strip().lower()
        return f"{cleaned_nim}@{self.auth_email_domain}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()

