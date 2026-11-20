"""Repository for `foto_wajah` (pgvector embeddings only; no raw photos)."""

from collections.abc import Sequence
from typing import Any

from app.core.exceptions import ExternalServiceError
from app.db.repositories.base import BaseRepository

EMBEDDING_DIMENSION = 512


def parse_embedding(value: Any) -> list[float]:
    """Parse a pgvector literal (`[0.1,0.2]`) or a legacy JSON list into floats."""
    if isinstance(value, (list, tuple)):
        return [float(v) for v in value]
    if isinstance(value, str):
        raw = value.strip()
        if raw.startswith("[") and raw.endswith("]"):
            raw = raw[1:-1]
        if not raw.strip():
            return []
        try:
            return [float(part.strip()) for part in raw.split(",") if part.strip()]
        except ValueError as exc:
            raise ExternalServiceError("Format embedding wajah tidak dikenali.") from exc
    return []


def to_vector_literal(values: Sequence[float]) -> str:
    """Validate a 512-D embedding and serialize it to a pgvector literal."""
    try:
        parsed = [float(v) for v in values]
    except (TypeError, ValueError) as exc:
        raise ExternalServiceError("Embedding wajah tidak valid.") from exc
    if len(parsed) != EMBEDDING_DIMENSION:
        raise ExternalServiceError(
            f"Dimensi embedding wajah harus {EMBEDDING_DIMENSION}, diterima {len(parsed)}."
        )
    return "[" + ",".join(repr(v) for v in parsed) + "]"


class FotoWajahRepository(BaseRepository):
    """Database operations for student face embeddings."""

    def list_by_nim(self, nim: str, active_only: bool = True) -> list[dict[str, Any]]:
        """Fetch face rows for a student with `embedding` parsed as floats."""
        query = self.client.table("foto_wajah").select("*").eq("nim", nim)
        if active_only:
            query = query.eq("is_active", True)
        res = query.order("created_at", desc=False).execute()
        rows = res.data or []
        for row in rows:
            row["embedding"] = parse_embedding(row.get("embedding"))
        return rows

    def create_many(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Bulk insert face embeddings as pgvector literals."""
        if not rows:
            return []
        payload = [
            {**row, "embedding": to_vector_literal(row.get("embedding", []))}
            for row in rows
        ]
        try:
            res = self.client.table("foto_wajah").insert(payload).execute()
            return res.data or []
        except Exception as exc:
            raise ExternalServiceError(f"Gagal menyimpan embedding wajah ke database: {exc}") from exc

    def deactivate_by_nim(self, nim: str) -> list[dict[str, Any]]:
        """Mark all active face rows for a student as inactive; return prior rows."""
        previous = self.list_by_nim(nim, active_only=True)
        if previous:
            self.client.table("foto_wajah").update({"is_active": False}).eq("nim", nim).eq("is_active", True).execute()
        return previous

    def delete_by_nim(self, nim: str) -> list[dict[str, Any]]:
        """Delete all `foto_wajah` rows for a student."""
        existing = self.list_by_nim(nim, active_only=False)
        if existing:
            self.client.table("foto_wajah").delete().eq("nim", nim).execute()
        return existing
