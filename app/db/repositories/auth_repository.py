"""Repository for Supabase Auth (GoTrue) user lifecycle and password verification."""

from typing import Any

from app.core.exceptions import ConflictError, ExternalServiceError
from app.db.repositories.base import BaseRepository
from app.db.session import create_auth_client


class AuthRepository(BaseRepository):
    """Encapsulates Supabase Auth Admin operations and credential verification."""

    def create_auth_user(
        self,
        email: str,
        password: str,
        user_metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a confirmed user in Supabase Auth and return its UUID."""
        try:
            res = self.client.auth.admin.create_user(
                {
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": user_metadata or {},
                }
            )
            user = getattr(res, "user", None)
            if not user or not getattr(user, "id", None):
                raise ExternalServiceError("Supabase Auth tidak mengembalikan user ID.")
            return str(user.id)
        except ExternalServiceError:
            raise
        except Exception as exc:
            msg = str(exc).lower()
            if "already" in msg or "exists" in msg or "registered" in msg:
                raise ConflictError("Akun autentikasi untuk email/NIM tersebut sudah ada.") from exc
            raise ExternalServiceError(f"Gagal membuat akun Supabase Auth: {exc}") from exc

    def link_student_auth_user(self, auth_user_id: str, nim: str) -> None:
        """Link a Supabase Auth UUID to `mahasiswa.auth_user_id` via SQL RPC."""
        try:
            self.client.rpc(
                "link_auth_user",
                {
                    "p_auth_user_id": auth_user_id,
                    "p_peran": "mahasiswa",
                    "p_identifier": nim,
                },
            ).execute()
        except Exception as exc:
            raise ExternalServiceError(f"Gagal menautkan auth user ke mahasiswa: {exc}") from exc

    def verify_credentials(self, email: str, password: str) -> str | None:
        """Verify email + password against Supabase GoTrue using a disposable client."""
        auth_client = create_auth_client(self.settings)
        try:
            res = auth_client.auth.sign_in_with_password({"email": email, "password": password})
            user = getattr(res, "user", None)
            return str(user.id) if user and getattr(user, "id", None) else None
        except Exception:
            return None

    def update_auth_password(self, auth_user_id: str, new_password: str) -> None:
        """Update password in Supabase Auth for the given user UUID."""
        try:
            self.client.auth.admin.update_user_by_id(auth_user_id, {"password": new_password})
        except Exception as exc:
            raise ExternalServiceError(f"Gagal memperbarui password di Supabase Auth: {exc}") from exc

    def update_auth_email(self, auth_user_id: str, new_email: str) -> None:
        """Update email in Supabase Auth for the given user UUID."""
        try:
            self.client.auth.admin.update_user_by_id(
                auth_user_id,
                {"email": new_email, "email_confirm": True},
            )
        except Exception as exc:
            raise ExternalServiceError(f"Gagal memperbarui email di Supabase Auth: {exc}") from exc

    def delete_auth_user(self, auth_user_id: str) -> None:
        """Delete a user from Supabase Auth."""
        try:
            self.client.auth.admin.delete_user(auth_user_id)
        except Exception as exc:
            raise ExternalServiceError(f"Gagal menghapus akun Supabase Auth: {exc}") from exc

    def find_auth_user_id_by_email(self, email: str) -> str | None:
        """Find a Supabase Auth user ID by email via admin pagination."""
        target = email.strip().lower()
        page = 1
        while True:
            users = self.client.auth.admin.list_users(page=page, per_page=200)
            if not users:
                return None
            for user in users:
                if (getattr(user, "email", None) or "").strip().lower() == target:
                    return str(user.id)
            if len(users) < 200:
                return None
            page += 1

