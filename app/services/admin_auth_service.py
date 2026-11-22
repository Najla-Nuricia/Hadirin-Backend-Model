"""Admin authentication backed exclusively by Supabase Auth."""

from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError, UnauthorizedError
from app.core.security import create_access_token, hash_password
from app.db.repositories import AdminRepository, AuthRepository
from app.schemas.admin_auth import (
    AdminChangeEmailRequest,
    AdminChangePasswordRequest,
    AdminLoginRequest,
    AdminLoginResponse,
)
from app.schemas.auth import MessageResponse


class AdminAuthService:
    """Verify admin credentials via Supabase Auth and issue admin-scoped JWT tokens."""

    def __init__(
        self,
        auth_repo: AuthRepository,
        admin_repo: AdminRepository,
        settings: Settings | None = None,
    ) -> None:
        self.auth_repo = auth_repo
        self.admin_repo = admin_repo
        self.settings = settings or get_settings()

    def login(self, payload: AdminLoginRequest) -> AdminLoginResponse:
        """Authenticate against Supabase Auth, confirm the admin link, then issue JWT."""
        email = self._resolve_email(payload.username)
        auth_user_id = self.auth_repo.verify_credentials(email, payload.password)
        if not auth_user_id or not self.admin_repo.get_by_auth_user_id(auth_user_id):
            raise UnauthorizedError("Username atau password admin salah.")

        token = create_access_token(
            subject=self.settings.admin_username,
            role="admin",
            extra_claims={
                "nim": None,
                "username": self.settings.admin_username,
                "name": "Administrator",
                "auth_user_id": auth_user_id,
            },
            settings=self.settings,
        )
        return AdminLoginResponse(
            username=self.settings.admin_username,
            name="Administrator",
            role="Admin",
            token=token,
            access_token=token,
            expires_in=self.settings.jwt_expire_minutes * 60,
        )

    def change_password(
        self,
        current_admin: dict[str, Any],
        payload: AdminChangePasswordRequest,
    ) -> MessageResponse:
        """Verify the current password, then update the admin password in Supabase Auth."""
        if payload.confirm_password is not None and payload.new_password != payload.confirm_password:
            raise BadRequestError("Konfirmasi password baru tidak cocok.")
        if payload.new_password == payload.current_password:
            raise BadRequestError("Password baru tidak boleh sama dengan password saat ini.")

        email = self._current_email(current_admin)
        if not self.auth_repo.verify_credentials(email, payload.current_password):
            raise BadRequestError("Password saat ini tidak sesuai.")

        hash_password(payload.new_password)
        self.auth_repo.update_auth_password(self._resolve_auth_user_id(current_admin), payload.new_password)
        return MessageResponse(message="Password admin berhasil diubah.")

    def change_email(
        self,
        current_admin: dict[str, Any],
        payload: AdminChangeEmailRequest,
    ) -> MessageResponse:
        """Verify the current password, then sync the new email to Auth and the admin row."""
        old_email = self._current_email(current_admin)
        if not self.auth_repo.verify_credentials(old_email, payload.current_password):
            raise BadRequestError("Password saat ini tidak sesuai.")

        new_email = payload.new_email.strip().lower()
        if new_email == old_email.strip().lower():
            raise BadRequestError("Email baru tidak boleh sama dengan email saat ini.")
        if self.admin_repo.get_by_email(new_email) or self.auth_repo.find_auth_user_id_by_email(new_email):
            raise ConflictError("Email sudah digunakan oleh akun lain.")

        auth_user_id = self._resolve_auth_user_id(current_admin)
        self.auth_repo.update_auth_email(auth_user_id, new_email)
        try:
            self.admin_repo.update_email(auth_user_id, new_email)
        except Exception:
            # Best-effort rollback: Auth is the source of truth, keep both stores in sync.
            try:
                self.auth_repo.update_auth_email(auth_user_id, old_email)
            except Exception:
                pass
            raise
        return MessageResponse(message="Email admin berhasil diubah.")

    def _current_email(self, current_admin: dict[str, Any]) -> str:
        """Return the admin's active email from the linked row, falling back to config."""
        row = self.admin_repo.get_by_auth_user_id(self._resolve_auth_user_id(current_admin))
        if row and row.get("email"):
            return str(row["email"])
        return self.settings.admin_email.strip().lower()

    def _resolve_auth_user_id(self, current_admin: dict[str, Any]) -> str:
        """Return the Supabase Auth UUID from the JWT claim or the linked admin row."""
        auth_user_id = str(current_admin.get("auth_user_id") or "").strip()
        if auth_user_id:
            return auth_user_id

        rows = self.admin_repo.list_all()
        if not rows or not rows[0].get("auth_user_id"):
            raise NotFoundError("Akun admin tidak ditemukan.")
        return str(rows[0]["auth_user_id"])

    def _resolve_email(self, identifier: str) -> str:
        """Map a username or email identifier to a Supabase Auth email."""
        value = identifier.strip()
        if "@" in value:
            return value.lower()

        lowered = value.lower()
        if lowered == self.settings.admin_username.strip().lower():
            # Prefer the current email in the admin row so username login keeps
            # working after the admin changes their email.
            current = self.admin_repo.get_by_email(self.settings.admin_email) or (
                self.admin_repo.list_all() or [None]
            )[0]
            if current and current.get("email"):
                return str(current["email"]).strip().lower()
            return self.settings.admin_email.strip().lower()
        return f"{lowered}@{self.settings.auth_email_domain}"
