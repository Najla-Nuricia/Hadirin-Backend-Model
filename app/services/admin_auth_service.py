"""Admin authentication backed exclusively by Supabase Auth."""

from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token
from app.db.repositories import AdminRepository, AuthRepository
from app.schemas.admin_auth import AdminLoginRequest, AdminLoginResponse


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

    def _resolve_email(self, identifier: str) -> str:
        """Map a username or email identifier to a Supabase Auth email."""
        value = identifier.strip()
        if "@" in value:
            return value.lower()

        lowered = value.lower()
        if lowered == self.settings.admin_username.strip().lower():
            return self.settings.admin_email.strip().lower()
        return f"{lowered}@{self.settings.auth_email_domain}"
