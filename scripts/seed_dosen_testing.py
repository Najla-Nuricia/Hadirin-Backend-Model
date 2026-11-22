"""Idempotent seed for the `Dosen Testing` account and its teaching schedule.

Creates (only if missing):
  * one `dosen` profile + one Supabase Auth user (`dosentesting@hadirin.test`)
    linked through `dosen.auth_user_id`;
  * a dense Senin-Jumat schedule taught by that single lecturer, covering every
    `kelas` and every `ruangan` already present in the database.

Pre-existing application rows are never updated or deleted; re-running produces the
same deterministic schedule IDs and skips rows that already exist. The dedicated
dummy Auth password is restored to `dosen123` if it was changed.

Usage:
    python -m scripts.seed_dosen_testing --dry-run   # preview only, no writes
    python -m scripts.seed_dosen_testing             # apply seed
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Any
import uuid

from app.core.config import Settings, get_settings
from app.db.repositories import AuthRepository
from app.db.session import get_supabase_client

TEST_EMAIL = "dosentesting@hadirin.test"
TEST_PASSWORD = "dosen123"
TEST_NAMA = "Dosen Testing"
TEST_NIP = "999999999001"

# Stable namespace so schedule UUIDs are identical on every run.
SEED_NAMESPACE = uuid.UUID("6f0a4c2e-9d31-4b18-8f7a-2c5e1d3b4a90")
HARI = ("senin", "selasa", "rabu", "kamis", "jumat")

Slot = tuple[int, int]
Occupancy = dict[tuple[str, str], list[Slot]]


def _overlaps(a: Slot, b: Slot) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def _is_free(occupancy: Occupancy, key: tuple[str, str], slot: Slot) -> bool:
    return not any(_overlaps(slot, used) for used in occupancy.get(key, []))


def _mark(occupancy: Occupancy, key: tuple[str, str], slot: Slot) -> None:
    occupancy.setdefault(key, []).append(slot)


def _fetch_reference_data(client: Any) -> dict[str, Any]:
    """Read every relation the seed needs. Never writes."""
    tahun = (
        client.table("tahun_ajaran")
        .select("id, tahun, status, semester_ganjil, semester_genap")
        .eq("status", "aktif")
        .execute()
        .data
        or []
    )
    if len(tahun) != 1:
        raise RuntimeError(f"Expected exactly 1 active tahun_ajaran, found {len(tahun)}.")

    kelas = (
        client.table("kelas")
        .select("id, nama, tingkat, program_studi_kode, tahun_ajaran_id")
        .order("tingkat")
        .order("nama")
        .execute()
        .data
        or []
    )
    ruangan = (
        client.table("ruangan").select("kode, nama").order("kode").execute().data or []
    )
    matkul = (
        client.table("mata_kuliah")
        .select("kode, nama, semester")
        .order("kode")
        .execute()
        .data
        or []
    )
    sesi = (
        client.table("sesi_kuliah")
        .select("nomor, jam_mulai, jam_selesai")
        .order("nomor")
        .execute()
        .data
        or []
    )
    if not kelas or not ruangan or not matkul or not sesi:
        raise RuntimeError("Reference data (kelas/ruangan/mata_kuliah/sesi_kuliah) is empty.")

    return {
        "tahun": tahun[0],
        "kelas": kelas,
        "ruangan": ruangan,
        "matkul": matkul,
        "sesi": sesi,
    }


def _build_blocks(sesi: list[dict[str, Any]]) -> list[Slot]:
    """Pair consecutive sessions: 1-2, 3-4, ... covering pagi sampai sore."""
    numbers = sorted(int(s["nomor"]) for s in sesi)
    blocks = [
        (numbers[i], numbers[i + 1]) for i in range(0, len(numbers) - 1, 2)
    ]
    if len(numbers) % 2:
        blocks.append((numbers[-1], numbers[-1]))
    return blocks


def _pick_matkul(
    kelas: dict[str, Any],
    occurrence: int,
    matkul: list[dict[str, Any]],
) -> dict[str, Any]:
    """Pick a course appropriate to the class level, rotating on each occurrence."""
    tingkat = int(kelas["tingkat"])
    candidates = [
        m for m in matkul if int(m["semester"]) in (tingkat * 2 - 1, tingkat * 2)
    ] or matkul
    return candidates[occurrence % len(candidates)]


def _build_assignments(
    refs: dict[str, Any],
    occupancy_kelas: Occupancy,
    occupancy_ruangan: Occupancy,
) -> list[dict[str, Any]]:
    """Deterministically plan schedules, skipping combinations that would clash."""
    kelas_list: list[dict[str, Any]] = refs["kelas"]
    ruangan_list: list[dict[str, Any]] = refs["ruangan"]
    matkul: list[dict[str, Any]] = refs["matkul"]
    blocks = _build_blocks(refs["sesi"])
    tahun = refs["tahun"]
    semester = "ganjil" if tahun["semester_ganjil"] else "genap"

    rows: list[dict[str, Any]] = []
    matkul_occurrence: dict[str, int] = defaultdict(int)
    sequence = 0

    for day_idx, hari in enumerate(HARI):
        for block_idx, slot in enumerate(blocks):
            turn = day_idx * len(blocks) + block_idx
            k_start = turn % len(kelas_list)
            r_start = (turn + 3) % len(ruangan_list)

            chosen_kelas = chosen_ruangan = None
            for k_step in range(len(kelas_list)):
                k = kelas_list[(k_start + k_step) % len(kelas_list)]
                if not _is_free(occupancy_kelas, (hari, k["id"]), slot):
                    continue
                for r_step in range(len(ruangan_list)):
                    r = ruangan_list[(r_start + r_step) % len(ruangan_list)]
                    if not _is_free(occupancy_ruangan, (hari, r["kode"]), slot):
                        continue
                    chosen_kelas, chosen_ruangan = k, r
                    break
                if chosen_kelas is not None:
                    break

            if chosen_kelas is None or chosen_ruangan is None:
                raise RuntimeError(
                    f"No conflict-free kelas/ruangan left for {hari} slot {slot}."
                )

            m = _pick_matkul(chosen_kelas, matkul_occurrence[chosen_kelas["id"]], matkul)
            matkul_occurrence[chosen_kelas["id"]] += 1

            seed_key = (
                f"hadirin-testing:v1:{TEST_NIP}:{hari}:{slot[0]}-{slot[1]}:"
                f"{chosen_kelas['id']}:{chosen_ruangan['kode']}:{m['kode']}:{sequence}"
            )
            rows.append(
                {
                    "id": str(uuid.uuid5(SEED_NAMESPACE, seed_key)),
                    "tahun_ajaran_id": tahun["id"],
                    "mata_kuliah_kode": m["kode"],
                    "dosen_nip": TEST_NIP,
                    "program_studi_kode": chosen_kelas["program_studi_kode"],
                    "kelas_id": chosen_kelas["id"],
                    "ruangan_kode": chosen_ruangan["kode"],
                    "hari": hari,
                    "sesi_mulai": slot[0],
                    "sesi_selesai": slot[1],
                    "semester": semester,
                }
            )
            _mark(occupancy_kelas, (hari, chosen_kelas["id"]), slot)
            _mark(occupancy_ruangan, (hari, chosen_ruangan["kode"]), slot)
            sequence += 1

    _fill_coverage_gaps(rows, refs, occupancy_kelas, occupancy_ruangan, sequence)
    return rows


def _fill_coverage_gaps(
    rows: list[dict[str, Any]],
    refs: dict[str, Any],
    occupancy_kelas: Occupancy,
    occupancy_ruangan: Occupancy,
    sequence: int,
) -> None:
    """Ensure every kelas gets >=3 meetings and every ruangan >=1 meeting."""
    blocks = _build_blocks(refs["sesi"])
    tahun = refs["tahun"]
    semester = "ganjil" if tahun["semester_ganjil"] else "genap"
    matkul: list[dict[str, Any]] = refs["matkul"]

    for min_meetings, entities, key_field, occupancy in (
        (3, refs["kelas"], "id", occupancy_kelas),
        (1, refs["ruangan"], "kode", occupancy_ruangan),
    ):
        for entity in entities:
            identifier = entity[key_field]
            row_field = "kelas_id" if key_field == "id" else "ruangan_kode"

            def meeting_count() -> int:
                return sum(1 for r in rows if r[row_field] == identifier)

            while meeting_count() < min_meetings:
                placed = False
                for hari in HARI:
                    for block_idx, slot in enumerate(blocks):
                        if not _is_free(occupancy, (hari, identifier), slot):
                            continue
                        if key_field == "id":
                            k, r = entity, refs["ruangan"][block_idx % len(refs["ruangan"])]
                        else:
                            k = refs["kelas"][block_idx % len(refs["kelas"])]
                            r = entity
                        if not _is_free(occupancy_ruangan, (hari, r["kode"]), slot):
                            continue
                        if not _is_free(occupancy_kelas, (hari, k["id"]), slot):
                            continue
                        m = _pick_matkul(k, len(rows), matkul)
                        seed_key = (
                            f"hadirin-testing:v1:{TEST_NIP}:{hari}:{slot[0]}-{slot[1]}:"
                            f"{k['id']}:{r['kode']}:{m['kode']}:{sequence}"
                        )
                        rows.append(
                            {
                                "id": str(uuid.uuid5(SEED_NAMESPACE, seed_key)),
                                "tahun_ajaran_id": tahun["id"],
                                "mata_kuliah_kode": m["kode"],
                                "dosen_nip": TEST_NIP,
                                "program_studi_kode": k["program_studi_kode"],
                                "kelas_id": k["id"],
                                "ruangan_kode": r["kode"],
                                "hari": hari,
                                "sesi_mulai": slot[0],
                                "sesi_selesai": slot[1],
                                "semester": semester,
                            }
                        )
                        _mark(occupancy_kelas, (hari, k["id"]), slot)
                        _mark(occupancy_ruangan, (hari, r["kode"]), slot)
                        sequence += 1
                        placed = True
                        break
                    if placed:
                        break
                if not placed:
                    raise RuntimeError(
                        f"Cannot place additional meeting for {identifier} without a conflict."
                    )


def _validate_plan(refs: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    """Fail fast if the generated plan breaks any seed requirement."""
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Duplicate schedule IDs generated.")

    if any(r["dosen_nip"] != TEST_NIP for r in rows):
        raise RuntimeError("A generated schedule is not assigned to the dummy lecturer.")

    per_kelas: dict[str, int] = defaultdict(int)
    per_ruangan: dict[str, int] = defaultdict(int)
    per_hari: dict[str, list[Slot]] = defaultdict(list)
    matkul_per_kelas: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        per_kelas[r["kelas_id"]] += 1
        per_ruangan[r["ruangan_kode"]] += 1
        per_hari[r["hari"]].append((r["sesi_mulai"], r["sesi_selesai"]))
        matkul_per_kelas[r["kelas_id"]].add(r["mata_kuliah_kode"])

    if set(per_kelas) != {k["id"] for k in refs["kelas"]}:
        raise RuntimeError("Not every kelas appears in the generated plan.")
    if set(per_ruangan) != {r["kode"] for r in refs["ruangan"]}:
        raise RuntimeError("Not every ruangan appears in the generated plan.")
    if set(per_hari) != set(HARI):
        raise RuntimeError("Plan must cover Senin through Jumat.")
    if any(count < 3 for count in per_kelas.values()):
        raise RuntimeError("Every kelas needs at least 3 meetings.")
    if any(len(matkul) < 2 for matkul in matkul_per_kelas.values()):
        raise RuntimeError("Every kelas needs varied mata kuliah.")

    first, last = min(per_hari[HARI[0]])[0], max(per_hari[HARI[-1]])[1]
    for hari in HARI:
        slots = per_hari[hari]
        if len(slots) < 5 or min(s[0] for s in slots) != first or max(s[1] for s in slots) != last:
            raise RuntimeError(f"{hari} is not dense from pagi sampai sore.")
    print(f"[VALIDATE] {len(rows)} rows OK; {len(per_kelas)} kelas, "
          f"{len(per_ruangan)} ruangan, {len({r['mata_kuliah_kode'] for r in rows})} matkul")


def _existing_occupancy(client: Any) -> tuple[Occupancy, Occupancy, set[str]]:
    rows = (
        client.table("jadwal_kuliah")
        .select("id, dosen_nip, hari, sesi_mulai, sesi_selesai, kelas_id, ruangan_kode")
        .execute()
        .data
        or []
    )
    by_kelas: Occupancy = defaultdict(list)
    by_ruangan: Occupancy = defaultdict(list)
    for row in rows:
        # Our own rows are regenerated deterministically on every run and would
        # otherwise shift the plan (breaking idempotency).
        if row.get("dosen_nip") == TEST_NIP:
            continue
        slot = (int(row["sesi_mulai"]), int(row["sesi_selesai"]))
        _mark(by_kelas, (row["hari"], row["kelas_id"]), slot)
        _mark(by_ruangan, (row["hari"], row["ruangan_kode"]), slot)
    return by_kelas, by_ruangan, {str(r["id"]) for r in rows}


def _ensure_dosen(client: Any) -> dict[str, Any]:
    existing = (
        client.table("dosen")
        .select("nip, nama, email, auth_user_id")
        .or_(f"email.eq.{TEST_EMAIL},nip.eq.{TEST_NIP}")
        .execute()
        .data
        or []
    )
    if existing:
        row = existing[0]
        if row["nip"] != TEST_NIP or row["email"].lower() != TEST_EMAIL:
            raise RuntimeError(
                "A dosen row already matches NIP/email but with different values; "
                "refusing to modify or delete it."
            )
        print(f"[DOSEN] Reusing existing profile nip={row['nip']}")
        return row

    res = (
        client.table("dosen")
        .insert({"nip": TEST_NIP, "nama": TEST_NAMA, "email": TEST_EMAIL})
        .execute()
    )
    if not res.data:
        raise RuntimeError(f"Failed to insert dosen profile: {res}")
    print(f"[DOSEN] Created profile nip={TEST_NIP}")
    return res.data[0]


def _ensure_auth_user(auth_repo: AuthRepository) -> str:
    auth_id = auth_repo.find_auth_user_id_by_email(TEST_EMAIL)
    if auth_id:
        if not auth_repo.verify_credentials(TEST_EMAIL, TEST_PASSWORD):
            # This is the dedicated dummy account owned by this seed.
            auth_repo.update_auth_password(auth_id, TEST_PASSWORD)
            print("[AUTH] Reset password for existing dummy account")
        else:
            print(f"[AUTH] Reusing existing Auth user {auth_id}")
        return auth_id

    auth_id = auth_repo.create_auth_user(
        email=TEST_EMAIL,
        password=TEST_PASSWORD,
        user_metadata={"nip": TEST_NIP, "nama_lengkap": TEST_NAMA, "peran": "dosen"},
    )
    print(f"[AUTH] Created confirmed Auth user {auth_id}")
    return auth_id


def _link_auth_user(client: Any, dosen: dict[str, Any], auth_id: str) -> None:
    current = dosen.get("auth_user_id")
    if current == auth_id:
        print("[AUTH] Auth user already linked to dosen profile")
        return
    if current:
        raise RuntimeError(
            f"Dosen {TEST_NIP} is already linked to auth_user_id={current}; "
            "refusing to reassign. Remove/stale cleanup must be done manually."
        )
    res = client.rpc(
        "link_auth_user",
        {
            "p_auth_user_id": auth_id,
            "p_peran": "dosen",
            "p_identifier": TEST_NIP,
        },
    ).execute()
    result = res.data if isinstance(res.data, dict) else None
    if not result or not result.get("success"):
        raise RuntimeError(f"Failed to link Auth user to dosen: {result or res.data}")
    print("[AUTH] Linked Auth user to dosen profile via link_auth_user RPC")


def _insert_schedules(client: Any, rows: list[dict[str, Any]], existing_ids: set[str]) -> None:
    missing = [r for r in rows if r["id"] not in existing_ids]
    if not missing:
        print(f"[JADWAL] All {len(rows)} schedules already present; nothing inserted")
        return
    client.table("jadwal_kuliah").insert(missing).execute()
    print(f"[JADWAL] Inserted {len(missing)} new schedules (skipped {len(rows) - len(missing)})")


def _verify(client: Any, refs: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    joined = (
        client.table("v_jadwal_lengkap")
        .select("*")
        .eq("dosen_nip", TEST_NIP)
        .execute()
        .data
        or []
    )
    all_jadwal = (
        client.table("jadwal_kuliah")
        .select("id, hari, sesi_mulai, sesi_selesai, kelas_id, ruangan_kode")
        .execute()
        .data
        or []
    )
    # Only the seed rows must be conflict-free; pre-existing rows are left untouched.
    for new in rows:
        slot = (new["sesi_mulai"], new["sesi_selesai"])
        for other in all_jadwal:
            if str(other["id"]) == str(new["id"]):
                continue
            if other["hari"] != new["hari"]:
                continue
            if other["kelas_id"] != new["kelas_id"] and other["ruangan_kode"] != new["ruangan_kode"]:
                continue
            if _overlaps(slot, (int(other["sesi_mulai"]), int(other["sesi_selesai"]))):
                raise RuntimeError(
                    f"Seed schedule {new['id']} conflicts with {other['id']} "
                    f"on {new['hari']} ({new['kelas_id']}, {new['ruangan_kode']})"
                )

    covered_kelas = {r["kelas_nama"] for r in joined}
    covered_ruangan = {r["ruangan_kode"] for r in joined}
    expected_kelas = {k["nama"] for k in refs["kelas"]}
    expected_ruangan = {r["kode"] for r in refs["ruangan"]}
    if covered_kelas != expected_kelas:
        raise RuntimeError(f"Kelas coverage mismatch: missing {expected_kelas - covered_kelas}")
    if covered_ruangan != expected_ruangan:
        raise RuntimeError(
            f"Ruangan coverage mismatch: missing {expected_ruangan - covered_ruangan}"
        )

    counts: dict[str, int] = defaultdict(int)
    per_day: dict[str, int] = defaultdict(int)
    for r in joined:
        counts[r["kelas_nama"]] += 1
        per_day[r["hari"]] += 1
        if not all(
            r.get(field) for field in ("matkul_kode", "dosen_nip", "kelas_nama", "ruangan_kode")
        ):
            raise RuntimeError(f"Incomplete relation in joined row: {r}")

    print(f"[VERIFY] {len(joined)} schedules joined for {TEST_NAMA}")
    print(f"[VERIFY] per day: {dict(per_day)}")
    print(f"[VERIFY] per kelas: {dict(sorted(counts.items()))}")
    print(f"[VERIFY] all {len(expected_ruangan)} ruangan used, no class/room conflicts")


def run_seed(dry_run: bool = False, settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    client = get_supabase_client(cfg)
    auth_repo = AuthRepository(client=client, settings=cfg)

    refs = _fetch_reference_data(client)
    by_kelas, by_ruangan, existing_ids = _existing_occupancy(client)
    rows = _build_assignments(refs, by_kelas, by_ruangan)
    _validate_plan(refs, rows)
    print(f"[PLAN] {len(rows)} schedules across {len(HARI)} days")
    for hari in HARI:
        day_rows = [r for r in rows if r["hari"] == hari]
        print(
            f"[PLAN] {hari}: {len(day_rows)} meetings, "
            f"sesi {min(r['sesi_mulai'] for r in day_rows)}-"
            f"{max(r['sesi_selesai'] for r in day_rows)}"
        )

    if dry_run:
        print("[DRY RUN] No writes performed.")
        return

    dosen = _ensure_dosen(client)
    auth_id = _ensure_auth_user(auth_repo)
    _link_auth_user(client, dosen, auth_id)
    _insert_schedules(client, rows, existing_ids)
    _verify(client, refs, rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan and validate against live reference data without writing anything.",
    )
    args = parser.parse_args()
    run_seed(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
