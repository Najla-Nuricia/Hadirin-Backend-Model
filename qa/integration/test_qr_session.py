"""Integration tests for lecturer QR session lifecycle and dynamic expiration."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.config import Settings

JADWAL_TI3A = "33333333-0000-0000-0000-000000000001"
JADWAL_TI1A = "33333333-0000-0000-0000-000000000006"
DOSEN_TI1A_EMAIL = "ahmad.fauzi@polinema.ac.id"


def _scan(client: TestClient, headers: dict[str, str], qr_code: str):
    return client.post(
        "/attendance/qr",
        headers=headers,
        json={"code": qr_code},
    )


def test_student_can_scan_dynamic_qr_and_scans_are_idempotent(
    client: TestClient,
    temp_student: dict[str, object],
    open_session,
) -> None:
    sesi = open_session(JADWAL_TI3A)
    headers = temp_student["headers"]

    first = _scan(client, headers, sesi["qr_code"])  # type: ignore[arg-type]
    second = _scan(client, headers, sesi["qr_code"])  # type: ignore[arg-type]
    history = client.get("/attendance/history", headers=headers)  # type: ignore[arg-type]

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    body = first.json()
    assert body["method"] == "qr"
    assert body["nim"] == temp_student["nim"]
    assert body["status"] == "hadir"
    assert body["courseName"] == "Pemrograman Web Lanjut"
    assert body["kelas"] == "TI-3A"
    assert body["sesi_presensi_id"] == sesi["sesi_presensi_id"]
    assert history.status_code == 200
    assert history.json()["total"] == 1


def test_refreshing_qr_invalidates_previous_code(
    client: TestClient,
    temp_student: dict[str, object],
    dosen_headers: dict[str, str],
    open_session,
) -> None:
    sesi = open_session(JADWAL_TI3A)
    headers = temp_student["headers"]

    refreshed = client.post(
        f"/dosen/sesi-presensi/{sesi['sesi_presensi_id']}/qr",
        headers=dosen_headers,
    )

    assert refreshed.status_code == 200
    assert refreshed.json()["qr_code"] != sesi["qr_code"]
    assert _scan(client, headers, sesi["qr_code"]).status_code == 403  # type: ignore[arg-type]
    assert _scan(client, headers, refreshed.json()["qr_code"]).status_code == 200  # type: ignore[arg-type]


def test_qr_expires_after_its_ttl(
    client: TestClient,
    temp_student: dict[str, object],
    open_session,
    session_clock: dict,
    settings: Settings,
) -> None:
    sesi = open_session(JADWAL_TI3A)
    opened_at = session_clock["now"]
    headers = temp_student["headers"]

    session_clock["now"] = opened_at + timedelta(seconds=settings.qr_token_ttl_seconds - 1)
    before_expiry = _scan(client, headers, sesi["qr_code"])  # type: ignore[arg-type]

    session_clock["now"] = opened_at + timedelta(seconds=settings.qr_token_ttl_seconds)
    at_expiry = _scan(client, headers, sesi["qr_code"])  # type: ignore[arg-type]

    assert before_expiry.status_code == 200
    assert at_expiry.status_code == 403
    assert "kedaluwarsa" in at_expiry.json()["detail"]


def test_qr_of_another_class_and_no_class_are_rejected(
    client: TestClient,
    temp_student: dict[str, object],
    temp_student_no_class: dict[str, str],
    dosen_login,
    open_session,
) -> None:
    sesi_ti1a = open_session(JADWAL_TI1A, headers=dosen_login(DOSEN_TI1A_EMAIL))
    sesi_ti3a = open_session(JADWAL_TI3A)

    wrong_class = _scan(client, temp_student["headers"], sesi_ti1a["qr_code"])  # type: ignore[arg-type]
    no_class = _scan(client, temp_student_no_class["headers"], sesi_ti3a["qr_code"])

    assert wrong_class.status_code == 403
    assert wrong_class.json()["detail"] == "QR Code ini bukan untuk kelas Anda."
    assert no_class.status_code == 403
    assert no_class.json()["detail"] == "Akun Anda belum terdaftar di kelas."


def test_closed_session_and_past_day_refresh_behave_correctly(
    client: TestClient,
    temp_student: dict[str, object],
    dosen_login,
    dosen_headers: dict[str, str],
    open_session,
    session_clock: dict,
) -> None:
    sesi = open_session(JADWAL_TI3A)
    sesi_url = f"/dosen/sesi-presensi/{sesi['sesi_presensi_id']}"

    session_clock["now"] += timedelta(days=1)
    stale_refresh = client.post(f"{sesi_url}/qr", headers=dosen_headers)
    assert stale_refresh.status_code == 409

    closed = client.post(f"{sesi_url}/tutup", headers=dosen_headers)
    assert closed.status_code == 200
    assert closed.json()["is_open"] is False
    assert closed.json()["qr_code"] is None
    assert _scan(client, temp_student["headers"], sesi["qr_code"]).status_code == 403  # type: ignore[arg-type]

    other_lecturer = dosen_login(DOSEN_TI1A_EMAIL)
    assert client.post(f"{sesi_url}/tutup", headers=other_lecturer).status_code == 403
    assert (
        client.post(
            f"/dosen/jadwal/{JADWAL_TI3A}/sesi-presensi",
            headers=temp_student["headers"],  # type: ignore[arg-type]
        ).status_code
        == 403
    )
