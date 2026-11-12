from datetime import timedelta

from fastapi.testclient import TestClient

from app.main import QR_TOKEN_TTL_SECONDS

DOSEN_TI1A_EMAIL = "ahmad.fauzi@polinema.ac.id"
JADWAL_TI3A = "33333333-0000-0000-0000-000000000001"
JADWAL_TI1A = "33333333-0000-0000-0000-000000000006"


def scan(client: TestClient, headers: dict, code: str):
    return client.post("/attendance/qr", headers=headers, json={"code": code})


def test_open_session_creates_qr_for_today(client: TestClient, open_session) -> None:
    sesi = open_session(JADWAL_TI3A)

    assert sesi["jadwal_id"] == JADWAL_TI3A
    assert sesi["tanggal"] == "2099-01-05"
    assert sesi["course_name"] == "Pemrograman Web Lanjut"
    assert sesi["kelas"] == "TI-3A"
    assert sesi["is_open"] is True
    assert sesi["qr_code"]
    assert sesi["qr_expires_at"]
    assert sesi["qr_ttl_seconds"] == QR_TOKEN_TTL_SECONDS


def test_reopening_keeps_one_session_per_schedule_and_day(open_session) -> None:
    first = open_session(JADWAL_TI3A)
    second = open_session(JADWAL_TI3A)

    assert second["sesi_presensi_id"] == first["sesi_presensi_id"]
    assert second["qr_code"] != first["qr_code"]


def test_student_of_the_class_scans_valid_qr(
    client: TestClient, student_headers: dict, open_session
) -> None:
    sesi = open_session(JADWAL_TI3A)

    response = scan(client, student_headers, sesi["qr_code"])

    assert response.status_code == 200
    body = response.json()
    assert body["method"] == "qr"
    assert body["nim"] == "2341720001"
    assert body["status"] == "hadir"
    assert body["courseName"] == "Pemrograman Web Lanjut"
    assert body["kelas"] == "TI-3A"
    assert body["sesi_presensi_id"] == sesi["sesi_presensi_id"]


def test_scanning_twice_records_one_attendance(
    client: TestClient, student_headers: dict, open_session
) -> None:
    sesi = open_session(JADWAL_TI3A)

    first = scan(client, student_headers, sesi["qr_code"])
    second = scan(client, student_headers, sesi["qr_code"])
    history = client.get("/attendance/history", headers=student_headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(history.json()) == 1


def test_refreshing_qr_invalidates_previous_code(
    client: TestClient, student_headers: dict, dosen_headers: dict, open_session
) -> None:
    sesi = open_session(JADWAL_TI3A)

    refreshed = client.post(
        f"/dosen/sesi-presensi/{sesi['sesi_presensi_id']}/qr", headers=dosen_headers
    )

    assert refreshed.status_code == 200
    assert refreshed.json()["qr_code"] != sesi["qr_code"]
    assert scan(client, student_headers, sesi["qr_code"]).status_code == 403
    assert scan(client, student_headers, refreshed.json()["qr_code"]).status_code == 200


def test_qr_expires_after_its_ttl(
    client: TestClient, student_headers: dict, open_session, session_clock: dict
) -> None:
    sesi = open_session(JADWAL_TI3A)
    opened_at = session_clock["now"]

    session_clock["now"] = opened_at + timedelta(seconds=QR_TOKEN_TTL_SECONDS - 1)
    before_expiry = scan(client, student_headers, sesi["qr_code"])
    session_clock["now"] = opened_at + timedelta(seconds=QR_TOKEN_TTL_SECONDS)
    at_expiry = scan(client, student_headers, sesi["qr_code"])

    assert before_expiry.status_code == 200
    assert at_expiry.status_code == 403
    assert "kedaluwarsa" in at_expiry.json()["detail"]


def test_qr_of_another_class_is_rejected(
    client: TestClient, student_headers: dict, dosen_login, open_session
) -> None:
    sesi = open_session(JADWAL_TI1A, headers=dosen_login(DOSEN_TI1A_EMAIL))

    response = scan(client, student_headers, sesi["qr_code"])

    assert response.status_code == 403
    assert response.json()["detail"] == "QR Code ini bukan untuk kelas Anda."


def test_student_without_class_cannot_scan(
    client: TestClient, auth_headers: dict, open_session
) -> None:
    sesi = open_session(JADWAL_TI3A)

    response = scan(client, auth_headers, sesi["qr_code"])

    assert response.status_code == 403
    assert response.json()["detail"] == "Akun Anda belum terdaftar di kelas."


def test_closed_session_rejects_scan_and_refresh(
    client: TestClient, student_headers: dict, dosen_headers: dict, open_session
) -> None:
    sesi = open_session(JADWAL_TI3A)
    sesi_url = f"/dosen/sesi-presensi/{sesi['sesi_presensi_id']}"

    closed = client.post(f"{sesi_url}/tutup", headers=dosen_headers)
    closed_again = client.post(f"{sesi_url}/tutup", headers=dosen_headers)
    refresh = client.post(f"{sesi_url}/qr", headers=dosen_headers)

    assert closed.status_code == 200
    assert closed.json()["is_open"] is False
    assert closed.json()["qr_code"] is None
    assert closed_again.status_code == 200
    assert scan(client, student_headers, sesi["qr_code"]).status_code == 403
    assert refresh.status_code == 409


def test_qr_cannot_be_refreshed_after_the_session_day(
    client: TestClient, dosen_headers: dict, open_session, session_clock: dict
) -> None:
    sesi = open_session(JADWAL_TI3A)

    session_clock["now"] += timedelta(days=1)
    response = client.post(
        f"/dosen/sesi-presensi/{sesi['sesi_presensi_id']}/qr", headers=dosen_headers
    )

    assert response.status_code == 409


def test_lecturer_cannot_manage_sessions_of_another_lecturer(
    client: TestClient, dosen_login, open_session
) -> None:
    sesi = open_session(JADWAL_TI3A)
    other_lecturer = dosen_login(DOSEN_TI1A_EMAIL)
    sesi_url = f"/dosen/sesi-presensi/{sesi['sesi_presensi_id']}"

    open_other = client.post(
        f"/dosen/jadwal/{JADWAL_TI3A}/sesi-presensi", headers=other_lecturer
    )
    refresh_other = client.post(f"{sesi_url}/qr", headers=other_lecturer)
    close_other = client.post(f"{sesi_url}/tutup", headers=other_lecturer)

    assert open_other.status_code == 403
    assert refresh_other.status_code == 403
    assert close_other.status_code == 403


def test_student_cannot_open_session(
    client: TestClient, student_headers: dict, session_clock: dict
) -> None:
    response = client.post(
        f"/dosen/jadwal/{JADWAL_TI3A}/sesi-presensi", headers=student_headers
    )

    assert response.status_code == 403
