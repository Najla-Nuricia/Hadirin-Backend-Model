"""Supabase client session management."""

from functools import lru_cache

from supabase import Client, create_client

from app.core.config import Settings, get_settings


@lru_cache(maxsize=1)
def _build_cached_service_client(supabase_url: str, service_key: str) -> Client:
    """Create and cache a singleton Supabase service-role client.

    Never call `auth.sign_in_with_password` on this shared instance because
    GoTrue mutates the client's PostgREST Authorization header to the user JWT.
    """
    return create_client(supabase_url, service_key)


def get_supabase_client(settings: Settings | None = None) -> Client:
    """Return shared Supabase service-role client for DB, Storage, and Auth Admin."""
    cfg = settings or get_settings()
    return _build_cached_service_client(cfg.supabase_url, cfg.supabase_service_key)


def create_auth_client(settings: Settings | None = None) -> Client:
    """Return a disposable Supabase client strictly for user password sign-in checks."""
    cfg = settings or get_settings()
    return create_client(cfg.supabase_url, cfg.supabase_service_key)

