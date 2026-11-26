"""Integration tests for persistent one-session-per-jadwal lifecycle."""

from app.core.config import Settings
from app.db.session import get_supabase_client

JADWAL_COLUMNS = (
    "id, tahun_ajaran_id, mata_kuliah_kode, dosen_nip, program_studi_kode, "
    "kelas_id, ruangan_kode, hari, sesi_mulai, sesi_selesai, semester"
)


def _copy_jadwal(settings: Settings) -> tuple[str, dict]:
    client = get_supabase_client(settings)
    row = client.table("jadwal_kuliah").select(JADWAL_COLUMNS).limit(1).execute().data[0]
    payload = {key: value for key, value in row.items() if key != "id"}
    created = client.table("jadwal_kuliah").insert(payload).execute().data[0]
    return str(created["id"]), created


def test_jadwal_auto_creates_exactly_one_session(settings: Settings) -> None:
    client = get_supabase_client(settings)
    jadwal_id, _ = _copy_jadwal(settings)
    try:
        sessions = (
            client.table("sesi_presensi").select("id").eq("jadwal_id", jadwal_id).execute().data
            or []
        )
        assert len(sessions) == 1
    finally:
        client.table("jadwal_kuliah").delete().eq("id", jadwal_id).execute()


def test_jadwal_delete_removes_session_and_attendance(settings: Settings) -> None:
    client = get_supabase_client(settings)
    jadwal_id, _ = _copy_jadwal(settings)
    try:
        sesi = (
            client.table("sesi_presensi")
            .select("id")
            .eq("jadwal_id", jadwal_id)
            .limit(1)
            .execute()
            .data[0]
        )
        sesi_id = str(sesi["id"])
        client.table("kehadiran").insert(
            {
                "sesi_presensi_id": sesi_id,
                "nim": "2211001",
                "tanggal": "2099-03-01",
                "status": "hadir",
            }
        ).execute()

        client.table("jadwal_kuliah").delete().eq("id", jadwal_id).execute()

        assert not (
            client.table("sesi_presensi").select("id").eq("id", sesi_id).execute().data
        )
        assert not (
            client.table("kehadiran")
            .select("id")
            .eq("sesi_presensi_id", sesi_id)
            .execute()
            .data
        )
    finally:
        client.table("jadwal_kuliah").delete().eq("id", jadwal_id).execute()
