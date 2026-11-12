import pytest
from fastapi.testclient import TestClient

from app import main

DOSEN_TI3A_EMAIL = "budi.santoso@polinema.ac.id"
DOSEN_TI3A_NIP = "198501012010121001"
JADWAL_TI3A = "33333333-0000-0000-0000-000000000001"
JADWAL_DOSEN_LAIN = "33333333-0000-0000-0000-000000000002"
JADWAL_TIDAK_ADA = "33333333-0000-0000-0000-00000000ffff"
TANGGAL_SESI_SEED = "2026-10-06"
STATUSES = ("hadir", "izin", "sakit", "alfa")


def test_dosen_login_returns_token_and_profile(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "DOSEN_DEFAULT_PASSWORD", "rahasia-dosen")

    response = client.post(
        "/auth/dosen/login",
        json={"email": "  Budi.Santoso@polinema.ac.id ", "password": "rahasia-dosen"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["nip"] == DOSEN_TI3A_NIP
    assert body["staffId"] == DOSEN_TI3A_NIP
    assert body["fullName"] == "Budi Santoso, S.T., M.T."
    assert body["role"] == "Dosen"


@pytest.mark.parametrize(
    ("email", "password"),
    [
        (DOSEN_TI3A_EMAIL, "password-salah"),
        ("tidak.ada@polinema.ac.id", "rahasia-dosen"),
        ("%", "rahasia-dosen"),
    ],
)
def test_dosen_login_rejects_wrong_credentials(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, email: str, password: str
) -> None:
    monkeypatch.setattr(main, "DOSEN_DEFAULT_PASSWORD", "rahasia-dosen")

    response = client.post(
        "/auth/dosen/login", json={"email": email, "password": password}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Email atau password salah."


def test_dosen_login_is_disabled_without_configured_password(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "DOSEN_DEFAULT_PASSWORD", "")

    response = client.post(
        "/auth/dosen/login", json={"email": DOSEN_TI3A_EMAIL, "password": "apa-saja"}
    )

    assert response.status_code == 503


def test_dosen_endpoints_require_a_dosen_token(
    client: TestClient, student_headers: dict
) -> None:
    without_token = client.get("/dosen/dashboard")
    with_student_token = client.get("/dosen/dashboard", headers=student_headers)
    with_unknown_token = client.get(
        "/dosen/dashboard", headers={"Authorization": "Bearer jwt_tebakan"}
    )

    assert without_token.status_code == 401
    assert with_student_token.status_code == 403
    assert with_unknown_token.status_code == 401


def test_dosen_token_is_rejected_on_student_endpoints(
    client: TestClient, dosen_headers: dict
) -> None:
    response = client.get("/mahasiswa/me", headers=dosen_headers)

    assert response.status_code == 401


def test_dashboard_lists_classes_and_attendance_summary(
    client: TestClient, dosen_headers: dict
) -> None:
    response = client.get("/dosen/dashboard", headers=dosen_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["dosen"]["nip"] == DOSEN_TI3A_NIP
    assert body["total_kelas"] == len(body["kelas"])
    assert body["total_jadwal"] == len(body["jadwal"])

    kelas = {item["kelas"]: item for item in body["kelas"]}
    assert kelas["TI-3A"]["jumlah_mahasiswa"] > 0
    assert kelas["TI-3A"]["jumlah_jadwal"] >= 1

    jadwal = {item["jadwal_id"]: item for item in body["jadwal"]}
    web_lanjut = jadwal[JADWAL_TI3A]
    assert web_lanjut["course_name"] == "Pemrograman Web Lanjut"
    assert web_lanjut["kelas"] == "TI-3A"
    assert web_lanjut["hari"] == "senin"
    assert web_lanjut["start_time"] == "07:50"
    assert web_lanjut["end_time"] == "09:30"
    assert web_lanjut["jumlah_sesi"] >= 1
    assert web_lanjut["sesi_terakhir"] >= TANGGAL_SESI_SEED
    assert web_lanjut["ringkasan_kehadiran"]["hadir"] >= 7

    # Setiap sesi menghitung seluruh mahasiswa kelas, jadi total = mahasiswa x sesi.
    for item in body["jadwal"]:
        summary = item["ringkasan_kehadiran"]
        assert summary["total"] == item["jumlah_mahasiswa"] * item["jumlah_sesi"]
        assert sum(summary[status] for status in STATUSES) == summary["total"]

    overall = body["ringkasan_kehadiran"]
    for status in STATUSES:
        assert overall[status] == sum(
            item["ringkasan_kehadiran"][status] for item in body["jadwal"]
        )
        assert overall[status] == sum(
            item["ringkasan_kehadiran"][status] for item in body["kelas"]
        )
    assert 0 <= overall["persentase_kehadiran"] <= 100


def test_dashboard_only_contains_own_schedules(
    client: TestClient, dosen_headers: dict
) -> None:
    body = client.get("/dosen/dashboard", headers=dosen_headers).json()

    assert JADWAL_DOSEN_LAIN not in {item["jadwal_id"] for item in body["jadwal"]}


def test_dashboard_reports_today_and_open_session(
    client: TestClient, dosen_headers: dict, open_session
) -> None:
    before = client.get("/dosen/dashboard", headers=dosen_headers).json()
    sesi = open_session(JADWAL_TI3A)
    after = client.get("/dosen/dashboard", headers=dosen_headers).json()

    jadwal_before = {item["jadwal_id"]: item for item in before["jadwal"]}
    jadwal_after = {item["jadwal_id"]: item for item in after["jadwal"]}
    # Tanggal sentinel jatuh pada hari Senin, sama dengan hari jadwal ini.
    assert after["tanggal"] == "2099-01-05"
    assert after["hari"] == "senin"
    assert jadwal_after[JADWAL_TI3A]["hari_ini"] is True
    assert all(
        item["hari_ini"] is False for item in after["jadwal"] if item["hari"] != "senin"
    )
    assert jadwal_before[JADWAL_TI3A]["sesi_aktif_id"] is None
    assert jadwal_after[JADWAL_TI3A]["sesi_aktif_id"] == sesi["sesi_presensi_id"]
    assert (
        jadwal_after[JADWAL_TI3A]["jumlah_sesi"]
        == jadwal_before[JADWAL_TI3A]["jumlah_sesi"] + 1
    )


def test_attendance_list_shows_status_per_student(
    client: TestClient, dosen_headers: dict
) -> None:
    response = client.get(
        f"/dosen/jadwal/{JADWAL_TI3A}/kehadiran",
        params={"tanggal": TANGGAL_SESI_SEED},
        headers=dosen_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["className"] == "TI-3A"
    assert body["courseName"] == "Pemrograman Web Lanjut"
    assert body["date"] == TANGGAL_SESI_SEED
    assert body["is_open"] is False
    assert {student["className"] for student in body["students"]} == {"TI-3A"}

    students = {student["nim"]: student for student in body["students"]}
    assert students["2211001"]["name"] == "Adi Saputra"
    assert students["2211001"]["status"] == "hadir"
    assert students["2211001"]["checkInTime"] == "07:58"
    assert students["2211003"]["status"] == "izin"
    assert students["2211003"]["note"] == "Ada keperluan keluarga."
    assert students["2211003"]["pengajuan_status"] == "pending"
    assert students["2211005"]["status"] == "sakit"
    assert students["2211007"]["status"] == "alfa"
    # Mahasiswa kelas tanpa catatan kehadiran pada sesi ini dihitung alfa.
    assert students["2341720001"]["status"] == "alfa"
    assert students["2341720001"]["checkInTime"] is None

    summary = body["summary"]
    assert summary["total"] == len(body["students"])
    for status in STATUSES:
        assert summary[status] == sum(
            1 for student in body["students"] if student["status"] == status
        )


def test_attendance_list_defaults_to_latest_session(
    client: TestClient, dosen_headers: dict
) -> None:
    dashboard = client.get("/dosen/dashboard", headers=dosen_headers).json()
    latest = {item["jadwal_id"]: item for item in dashboard["jadwal"]}[JADWAL_TI3A]

    response = client.get(
        f"/dosen/jadwal/{JADWAL_TI3A}/kehadiran", headers=dosen_headers
    )

    assert response.status_code == 200
    assert response.json()["date"] == latest["sesi_terakhir"]


def test_attendance_list_rejects_schedule_of_another_lecturer(
    client: TestClient, dosen_headers: dict
) -> None:
    response = client.get(
        f"/dosen/jadwal/{JADWAL_DOSEN_LAIN}/kehadiran", headers=dosen_headers
    )

    assert response.status_code == 403


def test_attendance_list_returns_404_without_session_or_schedule(
    client: TestClient, dosen_headers: dict
) -> None:
    no_session = client.get(
        f"/dosen/jadwal/{JADWAL_TI3A}/kehadiran",
        params={"tanggal": "2099-01-06"},
        headers=dosen_headers,
    )
    no_schedule = client.get(
        f"/dosen/jadwal/{JADWAL_TIDAK_ADA}/kehadiran", headers=dosen_headers
    )
    malformed_id = client.get(
        "/dosen/jadwal/bukan-uuid/kehadiran", headers=dosen_headers
    )

    assert no_session.status_code == 404
    assert no_schedule.status_code == 404
    assert malformed_id.status_code == 422
