"""Idempotent Supabase Auth provisioning for admin and dosen roles.

Mahasiswa accounts are provisioned by ``scripts/seed_auth_and_demo.py``.
This script only creates/links the Auth users that back the other two roles.
Passwords come from environment settings and are never stored in the backend.

Usage:
    python -m scripts.seed_auth_all_roles --dry-run
    python -m scripts.seed_auth_all_roles
    python -m scripts.seed_auth_all_roles --reset-passwords
"""

import argparse
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import get_settings
from app.db.repositories import AdminRepository, AuthRepository
from app.db.session import get_supabase_client


def run(dry_run: bool = False, reset_passwords: bool = False) -> None:
    """Ensure admin and dosen rows have matching, linked Supabase Auth users."""
    settings = get_settings()
    client = get_supabase_client(settings)
    auth_repo = AuthRepository(client=client, settings=settings)
    admin_repo = AdminRepository(client=client)

    admin_row = admin_repo.get_by_email(settings.admin_email)
    if not admin_row:
        raise RuntimeError(
            f"Admin '{settings.admin_email}' tidak ada di tabel admin. Jalankan seed.sql dulu."
        )

    admin_auth_id = auth_repo.find_auth_user_id_by_email(settings.admin_email)
    if not admin_auth_id:
        print(f"[ADMIN] Creating Supabase Auth user for {settings.admin_email}")
        if not dry_run:
            admin_auth_id = auth_repo.create_auth_user(
                email=settings.admin_email,
                password=settings.admin_initial_password,
                user_metadata={"nama": admin_row["nama"], "peran": "admin"},
            )
    elif reset_passwords:
        print("[ADMIN] Resetting password to ADMIN_INITIAL_PASSWORD")
        if not dry_run:
            auth_repo.update_auth_password(admin_auth_id, settings.admin_initial_password)

    if admin_auth_id and not admin_row.get("auth_user_id"):
        print("[ADMIN] Linking Auth user to public.admin")
        if not dry_run:
            auth_repo.link_admin_auth_user(admin_auth_id, settings.admin_email)

    dosen_rows = (
        client.table("dosen")
        .select("nip,nama,email,auth_user_id")
        .execute()
        .data
        or []
    )
    for dosen in dosen_rows:
        email = (dosen.get("email") or "").strip().lower()
        nip = dosen.get("nip")
        if not email or not nip:
            continue

        auth_id = dosen.get("auth_user_id") or auth_repo.find_auth_user_id_by_email(email)
        if not auth_id:
            print(f"[DOSEN] Creating Supabase Auth user for {email}")
            if not dry_run:
                auth_id = auth_repo.create_auth_user(
                    email=email,
                    password=settings.dosen_initial_password,
                    user_metadata={"nip": nip, "nama": dosen.get("nama"), "peran": "dosen"},
                )
        elif reset_passwords:
            print(f"[DOSEN] Resetting password for {email}")
            if not dry_run:
                auth_repo.update_auth_password(str(auth_id), settings.dosen_initial_password)

        if auth_id and not dosen.get("auth_user_id"):
            print(f"[DOSEN] Linking Auth user for {nip}")
            if not dry_run:
                auth_repo.link_dosen_auth_user(str(auth_id), str(nip))

    print("[DONE] Admin/Dosen Supabase Auth provisioning selesai.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Tampilkan rencana tanpa menulis.")
    parser.add_argument(
        "--reset-passwords",
        action="store_true",
        help="Reset password admin/dosen ke nilai awal dari environment.",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, reset_passwords=args.reset_passwords)
