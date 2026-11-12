"""Integration tests for mahasiswa CRUD, schedules, reminders, summary, and surat izin uploads."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.repositories import MahasiswaRepository
from app.db.session import get_supabase_client


def test_mahasiswa_profile_jadwal_pengingat_summary(
    client: TestClient,
    seeded_auth_headers: dict[str, str],
) -> None:
    me_resp = client.get("/mahasiswa/me", headers=seeded_auth_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["nim"] == "24000001"
    assert me_resp.json()["kelas"] == "TI-3A"

    jadwal_resp = client.get("/mahasiswa/jadwal", headers=seeded_auth_headers)
    assert jadwal_resp.status_code == 200
    jadwal_payload = jadwal_resp.json()
    assert jadwal_payload["total"] >= 1
    assert all(item["kelas_nama"] == "TI-3A" for item in jadwal_payload["data"])

    pengingat_resp = client.get("/mahasiswa/pengingat", headers=seeded_auth_headers)
    assert pengingat_resp.status_code == 200
    pengingat_data = pengingat_resp.json()["data"]
    assert pengingat_data is not None
    assert pengingat_data["kelas_nama"] == "TI-3A"

    summary_resp = client.get("/mahasiswa/presensi/summary", headers=seeded_auth_headers)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["nim"] == "24000001"
    assert summary["total_pertemuan"] == (
        summary["hadir"] + summary["izin"] + summary["sakit"] + summary["alfa"]
    )


def test_seeded_student_summary_reflects_real_attendance(client: TestClient) -> None:
    # Seeded student `2211001` has real attendance records in `v_rekap_kehadiran`.
    login_resp = client.post(
        "/auth/login",
        json={"nim": "2211001", "password": "mahasiswa123"},
    )
    assert login_resp.status_code == 200
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    summary = client.get("/mahasiswa/presensi/summary", headers=headers).json()
    assert summary["nim"] == "2211001"
    assert summary["total_pertemuan"] >= 1
    assert summary["hadir"] >= 1


def test_mahasiswa_crud_lifecycle(
    client: TestClient,
    seeded_auth_headers: dict[str, str],
    settings: Settings,
) -> None:
    test_nim = f"2498{uuid4().hex[:6]}"
    try:
        create_resp = client.post(
            "/mahasiswa",
            json={
                "nim": test_nim,
                "nama_lengkap": "Integration Test Student",
                "email": f"{test_nim}@student.polinema.ac.id",
                "no_hp": "081234567890",
                "kelas": "TI-3A",
            },
            headers=seeded_auth_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        assert create_resp.json()["data"]["nim"] == test_nim

        list_resp = client.get("/mahasiswa", headers=seeded_auth_headers)
        assert list_resp.status_code == 200
        assert any(m["nim"] == test_nim for m in list_resp.json()["data"])

        get_resp = client.get(f"/mahasiswa/{test_nim}", headers=seeded_auth_headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["nama_lengkap"] == "Integration Test Student"

        upd_resp = client.put(
            f"/mahasiswa/{test_nim}",
            json={"nama_lengkap": "Integration Student Updated"},
            headers=seeded_auth_headers,
        )
        assert upd_resp.status_code == 200
        assert upd_resp.json()["data"]["nama_lengkap"] == "Integration Student Updated"

        del_resp = client.delete(f"/mahasiswa/{test_nim}", headers=seeded_auth_headers)
        assert del_resp.status_code == 200

        after_del = client.get(f"/mahasiswa/{test_nim}", headers=seeded_auth_headers)
        assert after_del.status_code == 404
    finally:
        repo = MahasiswaRepository(client=get_supabase_client(settings), settings=settings)
        if repo.get_by_nim(test_nim):
            repo.delete_by_nim(test_nim)


def test_pengajuan_multipart_upload_and_crud(
    client: TestClient,
    temp_student: dict[str, object],
) -> None:
    headers = temp_student["headers"]
    sample_pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    pengajuan_id: str | None = None

    try:
        # 1. Multipart submission uploading file to `dokumen-pengajuan` + inserting DB record.
        upload_resp = client.post(
            "/mahasiswa/pengajuan/upload",
            data={
                "jenis": "sakit",
                "alasan": "Demam tinggi dan istirahat dokter",
                "matakuliah": "Pemrograman Web",
                "tanggal": "2026-11-18",
            },
            files={"file": ("surat_dokter.pdf", sample_pdf, "application/pdf")},
            headers=headers,  # type: ignore[arg-type]
        )
        assert upload_resp.status_code == 201, upload_resp.text
        created = upload_resp.json()["data"]
        pengajuan_id = created["id"]
        assert created["jenis"] == "sakit"
        assert created["status_pengajuan"] == "pending"
        assert created["dokumen_path"].endswith(".pdf")
        assert created["dokumen_url"] is not None

        # 2. Listed under GET /mahasiswa/pengajuan.
        list_resp = client.get("/mahasiswa/pengajuan", headers=headers)  # type: ignore[arg-type]
        assert list_resp.status_code == 200
        assert any(row["id"] == pengajuan_id for row in list_resp.json()["data"])

        # 3. Updating reason and type succeeds.
        upd_resp = client.put(
            f"/mahasiswa/pengajuan/{pengajuan_id}",
            json={"jenis": "izin", "alasan": "Izin menghadiri acara keluarga"},
            headers=headers,  # type: ignore[arg-type]
        )
        assert upd_resp.status_code == 200
        assert upd_resp.json()["data"]["jenis"] == "izin"
    finally:
        if pengajuan_id:
            client.delete(
                f"/mahasiswa/pengajuan/{pengajuan_id}",
                headers=headers,  # type: ignore[arg-type]
            )


def test_pengajuan_json_and_standalone_dokumen_upload(
    client: TestClient,
    temp_student: dict[str, object],
    settings: Settings,
) -> None:
    headers = temp_student["headers"]
    sample_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\x00\x00"
        b"\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    pengajuan_id: str | None = None
    uploaded_path: str | None = None

    try:
        doc_resp = client.post(
            "/mahasiswa/pengajuan/dokumen",
            files={"file": ("bukti_izin.png", sample_png, "image/png")},
            headers=headers,  # type: ignore[arg-type]
        )
        assert doc_resp.status_code == 201, doc_resp.text
        uploaded_path = doc_resp.json()["dokumen_path"]
        assert doc_resp.json()["dokumen_url"] is not None

        create_resp = client.post(
            "/mahasiswa/pengajuan",
            json={
                "jenis": "izin",
                "alasan": "Mengikuti lomba nasional kampus",
                "matakuliah": "Pemrograman Web",
                "tanggal": "2026-11-22",
                "dokumen_path": uploaded_path,
            },
            headers=headers,  # type: ignore[arg-type]
        )
        assert create_resp.status_code == 201, create_resp.text
        pengajuan_id = create_resp.json()["data"]["id"]
        assert create_resp.json()["data"]["dokumen_path"] == uploaded_path
    finally:
        if pengajuan_id:
            client.delete(f"/mahasiswa/pengajuan/{pengajuan_id}", headers=headers)  # type: ignore[arg-type]
        elif uploaded_path:
            supabase = get_supabase_client(settings)
            supabase.storage.from_(settings.storage_bucket_pengajuan).remove([uploaded_path])
