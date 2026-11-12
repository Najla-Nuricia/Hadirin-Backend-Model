"""Integration tests for `Surat Izin`/`Sakit`/`Kompensasi` and Storage uploads."""

from uuid import uuid4

from fastapi.testclient import TestClient

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\xf8\x0f\x00"
    b"\x01\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_submit_izin_sakit_kompensasi_with_and_without_documents(
    client: TestClient,
    temp_student: dict[str, object],
) -> None:
    headers = temp_student["headers"]
    created_ids: list[str] = []

    try:
        # 1. Multipart upload with PDF for `sakit`
        sakit_resp = client.post(
            "/mahasiswa/pengajuan/upload",
            headers=headers,  # type: ignore[arg-type]
            data={
                "jenis": "sakit",
                "alasan": f"Demam test {uuid4().hex[:6]}",
                "matakuliah": "Pemrograman Web Lanjut",
                "tanggal": "2099-02-10",
            },
            files={"file": ("surat_dokter.pdf", MINIMAL_PDF, "application/pdf")},
        )
        assert sakit_resp.status_code == 201, sakit_resp.text
        sakit_data = sakit_resp.json()["data"]
        created_ids.append(sakit_data["id"])
        assert sakit_data["jenis"] == "sakit"
        assert sakit_data["dokumen_path"]
        assert sakit_data["dokumen_url"]

        # 2. Multipart upload WITHOUT extension & octet-stream MIME (byte-sniffed PNG for `kompensasi`)
        kompen_resp = client.post(
            "/mahasiswa/pengajuan/upload",
            headers=headers,  # type: ignore[arg-type]
            data={
                "jenis": "kompensasi",
                "alasan": "Surat kompensasi lab jaringan",
                "matakuliah": "Basis Data Lanjut",
                "tanggal": "2099-02-11",
            },
            files={"file": ("document_android_uri", MINIMAL_PNG, "application/octet-stream")},
        )
        assert kompen_resp.status_code == 201, kompen_resp.text
        kompen_data = kompen_resp.json()["data"]
        created_ids.append(kompen_data["id"])
        assert kompen_data["jenis"] == "kompensasi"
        assert kompen_data["dokumen_path"].endswith(".png")

        # 3. JSON request without document for `izin`
        izin_resp = client.post(
            "/mahasiswa/pengajuan",
            headers=headers,  # type: ignore[arg-type]
            json={
                "jenis": "izin",
                "alasan": "Acara keluarga resmi",
                "matakuliah": "Kecerdasan Buatan",
                "tanggal": "2099-02-12",
            },
        )
        assert izin_resp.status_code == 201, izin_resp.text
        created_ids.append(izin_resp.json()["data"]["id"])

        listed = client.get("/mahasiswa/pengajuan", headers=headers)  # type: ignore[arg-type]
        assert listed.status_code == 200
        assert listed.json()["total"] == 3
    finally:
        for pid in created_ids:
            client.delete(f"/mahasiswa/pengajuan/{pid}", headers=headers)  # type: ignore[arg-type]
