import pytest
from fastapi.testclient import TestClient

from app import main

DOSEN_TI3A_EMAIL = "budi.santoso@polinema.ac.id"
DOSEN_TI3A_NIP = "198501012010121001"
JADWAL_TI3A = "33333333-0000-0000-0000-000000000001"
JADWAL_DOSEN_LAIN = "33333333-0000-0000-0000-000000000002"
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
