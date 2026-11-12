"""Idempotent script to provision Supabase Auth users and link them to `mahasiswa` rows."""

import argparse
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import get_settings
from app.db.repositories import AuthRepository, MahasiswaRepository
from app.db.session import get_supabase_client

QA_DEMO_ACCOUNTS: list[dict[str, str]] = [
    {
        "nim": "24000001",
        "nama_lengkap": "Demo Student One",
        "email": "24000001@student.polinema.ac.id",
        "password": "password123",
        "kelas_nama": "TI-3A",
    },
    {
        "nim": "24000002",
        "nama_lengkap": "Demo Student Two",
        "email": "24000002@student.polinema.ac.id",
        "password": "password123",
        "kelas_nama": "TI-3A",
    },
]

TEST_ARTIFACT_NIMS = ("24000003", "24999999")


def _ensure_auth_linked(
    auth_repo: AuthRepository,
    nim: str,
    email: str,
    password: str,
    nama_lengkap: str,
    existing_auth_id: str | None,
    reset_passwords: bool,
) -> str:
    if existing_auth_id:
        if reset_passwords:
            auth_repo.update_auth_password(existing_auth_id, password)
        return existing_auth_id

    auth_id = auth_repo.find_auth_user_id_by_email(email)
    if not auth_id:
        auth_id = auth_repo.create_auth_user(
            email=email,
            password=password,
            user_metadata={"nim": nim, "nama_lengkap": nama_lengkap, "peran": "mahasiswa"},
        )
    elif reset_passwords:
        auth_repo.update_auth_password(auth_id, password)

    auth_repo.link_student_auth_user(auth_id, nim)
    return auth_id


def run_seed(default_student_password: str = "mahasiswa123", reset_passwords: bool = False) -> None:
    """Seed Auth accounts for `seed.sql` students and QA demo accounts in Supabase."""
    settings = get_settings()
    client = get_supabase_client(settings)
    mhs_repo = MahasiswaRepository(client=client, settings=settings)
    auth_repo = AuthRepository(client=client, settings=settings)

    # 1. Remove leftover transient test NIMs if any exist.
    for artifact_nim in TEST_ARTIFACT_NIMS:
        row = mhs_repo.get_by_nim(artifact_nim)
        if row:
            auth_id = row.get("auth_user_id")
            mhs_repo.delete_by_nim(artifact_nim)
            if auth_id:
                try:
                    auth_repo.delete_auth_user(str(auth_id))
                except Exception:
                    pass
            print(f"[CLEANUP] Removed leftover test student NIM {artifact_nim}")

    # 2. Ensure QA demo accounts exist with valid class and profile data.
    for demo in QA_DEMO_ACCOUNTS:
        kelas = mhs_repo.get_kelas_by_name(demo["kelas_nama"])
        kelas_id = kelas["id"] if kelas else None
        existing = mhs_repo.get_by_nim(demo["nim"])
        if existing:
            mhs_repo.update_by_nim(
                demo["nim"],
                {
                    "nama_lengkap": demo["nama_lengkap"],
                    "email": demo["email"],
                    "kelas_id": kelas_id or existing.get("kelas_id"),
                },
            )
        else:
            mhs_repo.create(
                {
                    "nim": demo["nim"],
                    "nama_lengkap": demo["nama_lengkap"],
                    "email": demo["email"],
                    "kelas_id": kelas_id,
                }
            )
        refreshed = mhs_repo.get_by_nim(demo["nim"])
        auth_id = _ensure_auth_linked(
            auth_repo=auth_repo,
            nim=demo["nim"],
            email=demo["email"],
            password=demo["password"],
            nama_lengkap=demo["nama_lengkap"],
            existing_auth_id=(refreshed or {}).get("auth_user_id"),
            reset_passwords=reset_passwords,
        )
        print(f"[QA DEMO] NIM={demo['nim']} ({demo['nama_lengkap']}) -> auth_user_id={auth_id}")

    # 3. Link every remaining student row that lacks an Auth account.
    for student in mhs_repo.list_all():
        nim = student["nim"]
        if any(demo["nim"] == nim for demo in QA_DEMO_ACCOUNTS):
            continue
        email = student.get("email") or settings.synthetic_email_for_nim(nim)
        auth_id = _ensure_auth_linked(
            auth_repo=auth_repo,
            nim=nim,
            email=email,
            password=default_student_password,
            nama_lengkap=student.get("nama_lengkap") or nim,
            existing_auth_id=student.get("auth_user_id"),
            reset_passwords=reset_passwords,
        )
        print(f"[SEED LINKED] NIM={nim} ({email}) -> auth_user_id={auth_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Provision Supabase Auth users for Hadirin students.")
    parser.add_argument(
        "--default-password",
        default="mahasiswa123",
        help="Default initial password for seeded mahasiswa rows without auth_user_id.",
    )
    parser.add_argument(
        "--reset-passwords",
        action="store_true",
        help="Also reset passwords for already-linked seeded/demo accounts.",
    )
    args = parser.parse_args()
    run_seed(default_student_password=args.default_password, reset_passwords=args.reset_passwords)

