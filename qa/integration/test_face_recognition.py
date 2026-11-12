"""Integration tests for MTCNN + MobileFaceNet registration, update, verify, and attendance."""

import base64
from datetime import datetime, timedelta, timezone
import io
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import Settings
from app.db.repositories import JadwalRepository, KehadiranRepository
from app.db.session import get_supabase_client

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "faces"


def _blank_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (200, 200), (255, 255, 255)).save(buf, format="JPEG")
    return buf.getvalue()


def test_face_registration_update_verify_and_attendance(
    client: TestClient,
    temp_student: dict[str, object],
    settings: Settings,
) -> None:
    headers = temp_student["headers"]
    nim = str(temp_student["nim"])

    sheldon_ref = (FIXTURES_DIR / "sheldon_ref.jpg").read_bytes()
    sheldon_probe = (FIXTURES_DIR / "sheldon_probe.jpg").read_bytes()
    leonard_probe = (FIXTURES_DIR / "leonard_probe.jpg").read_bytes()

    # 1. Initially unregistered.
    st0 = client.get("/mahasiswa/wajah/status", headers=headers)  # type: ignore[arg-type]
    assert st0.status_code == 200
    assert st0.json()["is_registered"] is False
    assert st0.json()["active_samples"] == 0

    # 2. Blank / no-face upload fails cleanly with 422.
    blank_resp = client.post(
        "/mahasiswa/wajah/register",
        files=[("files", ("blank.jpg", _blank_jpeg_bytes(), "image/jpeg"))],
        headers=headers,  # type: ignore[arg-type]
    )
    assert blank_resp.status_code == 422

    # 3. Valid face registration via multipart extracts 512-D embeddings & stores in Supabase.
    reg_resp = client.post(
        "/mahasiswa/wajah/register",
        files=[("files", ("sheldon_ref.jpg", sheldon_ref, "image/jpeg"))],
        headers=headers,  # type: ignore[arg-type]
    )
    assert reg_resp.status_code == 201, reg_resp.text
    reg_data = reg_resp.json()
    assert reg_data["samples_saved"] == 1
    assert reg_data["embedding_dimension"] == 512
    assert len(reg_data["storage_paths"]) == 1

    # 4. Duplicate registration blocked with 409 Conflict (must use PUT /update).
    dup_resp = client.post(
        "/mahasiswa/wajah/register",
        files=[("files", ("sheldon_ref.jpg", sheldon_ref, "image/jpeg"))],
        headers=headers,  # type: ignore[arg-type]
    )
    assert dup_resp.status_code == 409

    # 5. Same identity probe matches; different identity does not match.
    match_resp = client.post(
        "/mahasiswa/wajah/verify",
        files={"file": ("sheldon_probe.jpg", sheldon_probe, "image/jpeg")},
        headers=headers,  # type: ignore[arg-type]
    )
    assert match_resp.status_code == 200, match_resp.text
    assert match_resp.json()["matched"] is True
    assert match_resp.json()["similarity"] >= settings.face_similarity_threshold

    mismatch_resp = client.post(
        "/mahasiswa/wajah/verify",
        files={"file": ("leonard_probe.jpg", leonard_probe, "image/jpeg")},
        headers=headers,  # type: ignore[arg-type]
    )
    assert mismatch_resp.status_code == 200
    assert mismatch_resp.json()["matched"] is False
    assert mismatch_resp.json()["similarity"] < settings.face_similarity_threshold

    # 6. Face attendance against a real open `sesi_presensi` records `kehadiran` + snapshot photo.
    supabase = get_supabase_client(settings)
    jadwal_repo = JadwalRepository(client=supabase, settings=settings)
    kehadiran_repo = KehadiranRepository(client=supabase, settings=settings)
    jadwal = jadwal_repo.list_by_kelas_nama("TI-3A")[0]
    sesi = kehadiran_repo.create_sesi_presensi(
        {
            "jadwal_id": jadwal["id"],
            "tanggal": "2099-01-20",
            "qr_token": f"FACE_SESI_{uuid4().hex[:8]}",
            "qr_expires_at": (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat(),
            "is_open": True,
            "dibuka_oleh": jadwal.get("dosen_nip"),
        }
    )
    sesi_id = str(sesi["id"])

    try:
        # Different person rejected from face attendance check-in with 403.
        bad_att = client.post(
            "/attendance/face",
            data={"sesi_presensi_id": sesi_id},
            files={"file": ("leonard_probe.jpg", leonard_probe, "image/jpeg")},
            headers=headers,  # type: ignore[arg-type]
        )
        assert bad_att.status_code == 403

        # Matching person succeeds and writes `kehadiran` + uploads `face_photo_path`.
        ok_att = client.post(
            "/attendance/face",
            data={
                "sesi_presensi_id": sesi_id,
                "latitude": str(settings.campus_latitude),
                "longitude": str(settings.campus_longitude),
            },
            files={"file": ("sheldon_probe.jpg", sheldon_probe, "image/jpeg")},
            headers=headers,  # type: ignore[arg-type]
        )
        assert ok_att.status_code == 200, ok_att.text
        att_data = ok_att.json()
        assert att_data["status"] == "hadir"
        assert att_data["similarity"] >= settings.face_similarity_threshold
        assert att_data["face_photo_path"] is not None
    finally:
        existing_k = kehadiran_repo.get_kehadiran_by_sesi_and_nim(sesi_id, nim)
        if existing_k:
            kehadiran_repo.delete_attendance_photo(existing_k.get("face_photo_path"))
            kehadiran_repo.delete_kehadiran_by_id(str(existing_k["id"]))
        kehadiran_repo.delete_sesi_presensi(sesi_id)

    # 7. Updating face samples via base64 JSON replaces active template cleanly.
    leonard_b64 = base64.b64encode(leonard_probe).decode("ascii")
    upd_resp = client.put(
        "/mahasiswa/wajah/update",
        json={"images_base64": [leonard_b64]},
        headers=headers,  # type: ignore[arg-type]
    )
    assert upd_resp.status_code == 200, upd_resp.text
    assert upd_resp.json()["samples_saved"] == 1

    # Now Leonard matches and Sheldon no longer matches!
    leo_verify = client.post(
        "/mahasiswa/wajah/verify",
        files={"file": ("leonard_probe.jpg", leonard_probe, "image/jpeg")},
        headers=headers,  # type: ignore[arg-type]
    )
    assert leo_verify.status_code == 200
    assert leo_verify.json()["matched"] is True

    shel_verify = client.post(
        "/mahasiswa/wajah/verify",
        files={"file": ("sheldon_probe.jpg", sheldon_probe, "image/jpeg")},
        headers=headers,  # type: ignore[arg-type]
    )
    assert shel_verify.status_code == 200
    assert shel_verify.json()["matched"] is False

    # 8. Delete cleans up Storage & DB rows cleanly.
    del_resp = client.delete("/mahasiswa/wajah", headers=headers)  # type: ignore[arg-type]
    assert del_resp.status_code == 200
    st_final = client.get("/mahasiswa/wajah/status", headers=headers)  # type: ignore[arg-type]
    assert st_final.json()["is_registered"] is False

