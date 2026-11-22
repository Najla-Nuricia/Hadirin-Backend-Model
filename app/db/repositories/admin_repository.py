"""Repository for the `admin` table and its Supabase Auth linkage."""

from typing import Any

from app.db.repositories.base import BaseRepository


class AdminRepository(BaseRepository):
    """Read admin rows to authorize Supabase Auth users."""

    def get_by_auth_user_id(self, auth_user_id: str) -> dict[str, Any] | None:
        """Return the admin row linked to a Supabase Auth user ID, if any."""
        res = (
            self.client.table("admin")
            .select("id,nama,email,auth_user_id")
            .eq("auth_user_id", auth_user_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        """Return an admin row by its email address."""
        res = (
            self.client.table("admin")
            .select("id,nama,email,auth_user_id")
            .eq("email", email.strip().lower())
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None

    def update_email(self, auth_user_id: str, new_email: str) -> dict[str, Any] | None:
        """Update the admin row's email and return the updated row, if any."""
        res = (
            self.client.table("admin")
            .update({"email": new_email.strip().lower()})
            .eq("auth_user_id", auth_user_id)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None

    def list_all(self) -> list[dict[str, Any]]:
        """Return all admin rows (used by provisioning tooling)."""
        res = self.client.table("admin").select("id,nama,email,auth_user_id").execute()
        return res.data or []
