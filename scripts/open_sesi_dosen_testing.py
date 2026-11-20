"""Open one sesi presensi per jadwal of Dosen Testing, Senin-Jumat.

Sessions are dated to the weekday of each jadwal within a chosen week (default:
the current WIB week) and inserted with `is_open = true` and no QR token or
expiry, so they stay open indefinitely for testing.

Existing sessions are never modified; only missing (jadwal_id, tanggal) pairs
are inserted, so re-running within the same week is idempotent.

Usage:
    python -m scripts.open_sesi_dosen_testing --dry-run
    python -m scripts.open_sesi_dosen_testing
    python -m scripts.open_sesi_dosen_testing --monday 2026-11-23
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from typing import Any

from app.core.config import Settings, get_settings
from app.db.session import get_supabase_client
from app.services.common import HARI_ORDER, WIB
from scripts.seed_dosen_testing import TEST_EMAIL

WEEKDAYS = ("senin", "selasa", "rabu", "kamis", "jumat")


def _monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _build_rows(jadwal: list[dict[str, Any]], monday: date, nip: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for j in jadwal:
        hari = str(j["hari"]).lower()
        if hari not in WEEKDAYS:
            continue
        tanggal = monday + timedelta(days=HARI_ORDER[hari])
        rows.append(
            {
                "jadwal_id": j["id"],
                "tanggal": tanggal.isoformat(),
                "is_open": True,
                "dibuka_oleh": nip,
                "qr_token": None,
                "qr_expires_at": None,
            }
        )
    return rows


def run_open(monday: date | None = None, dry_run: bool = False, settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    client = get_supabase_client(cfg)

    dosen = (
        client.table("dosen")
        .select("nip, nama")
        .eq("email", TEST_EMAIL)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not dosen:
        raise RuntimeError(
            f"Dosen {TEST_EMAIL} belum ada. Jalankan `python -m scripts.seed_dosen_testing` dulu."
        )
    nip = str(dosen[0]["nip"])

    jadwal = (
        client.table("jadwal_kuliah").select("id, hari").eq("dosen_nip", nip).execute().data or []
    )
    start = monday or _monday_of(datetime.now(WIB).date())
    rows = _build_rows(jadwal, start, nip)
    if not rows:
        raise RuntimeError("Tidak ada jadwal Senin-Jumat untuk dosen ini.")

    existing = (
        client.table("sesi_presensi")
        .select("id, jadwal_id, tanggal")
        .in_("jadwal_id", [r["jadwal_id"] for r in rows])
        .execute()
        .data
        or []
    )
    existing_keys = {(e["jadwal_id"], str(e["tanggal"])[:10]) for e in existing}
    missing = [r for r in rows if (r["jadwal_id"], r["tanggal"]) not in existing_keys]

    print(f"[DOSEN] {dosen[0]['nama']} (nip={nip})")
    print(f"[PLAN] minggu mulai {start.isoformat()}: {len(rows)} target sesi, "
          f"{len(missing)} belum ada, {len(rows) - len(missing)} sudah ada")

    if dry_run:
        print("[DRY RUN] No writes performed.")
        return
    if not missing:
        print("[SESI] Semua sesi sudah ada; tidak ada yang dibuat.")
        return

    client.table("sesi_presensi").insert(missing).execute()
    print(f"[SESI] Dibuka {len(missing)} sesi presensi (is_open=true, tanpa QR/expiry)")

    opened = (
        client.table("sesi_presensi")
        .select("id, tanggal, is_open, jadwal_id")
        .in_("jadwal_id", [r["jadwal_id"] for r in rows])
        .execute()
        .data
        or []
    )
    per_day: dict[str, int] = {}
    for sesi in opened:
        if sesi["is_open"]:
            day = str(sesi["tanggal"])[:10]
            per_day[day] = per_day.get(day, 0) + 1
    print(f"[VERIFY] {sum(per_day.values())} sesi terbuka: {dict(sorted(per_day.items()))}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Hanya tampilkan rencana.")
    parser.add_argument(
        "--monday",
        type=date.fromisoformat,
        default=None,
        help="Tanggal Senin awal pekan (YYYY-MM-DD). Default: pekan berjalan (WIB).",
    )
    args = parser.parse_args()
    run_open(monday=args.monday, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
