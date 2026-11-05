from fastapi.testclient import TestClient


def test_load_mahasiswa_profile(client: TestClient, auth_headers: dict) -> None:
    # 2. Api load data mhs (Profile)
    response = client.get("/mahasiswa/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["nim"] == "24000001"
    assert data["role"] == "Mahasiswa"
    assert "className" in data
    assert "email" in data


def test_load_mahasiswa_jadwal(client: TestClient, auth_headers: dict) -> None:
    # 2. Api load data mhs (Jadwal)
    response = client.get("/mahasiswa/jadwal", headers=auth_headers)
    assert response.status_code == 200
    schedules = response.json()
    assert isinstance(schedules, list)
    assert len(schedules) > 0

    # Filter by day
    filtered = client.get("/mahasiswa/jadwal?day_of_week=3", headers=auth_headers)
    assert filtered.status_code == 200
    for s in filtered.json():
        assert s["day_of_week"] == 3


def test_load_mahasiswa_presensi_summary(client: TestClient, auth_headers: dict) -> None:
    # 2. Api load data mhs (Rekap Presensi)
    response = client.get("/mahasiswa/presensi/summary", headers=auth_headers)
    assert response.status_code == 200
    summary = response.json()
    assert "hadir" in summary
    assert "izin" in summary
    assert "sakit" in summary
    assert "alfa" in summary
    assert "persentase_kehadiran" in summary


def test_load_mahasiswa_pengingat(client: TestClient, auth_headers: dict) -> None:
    # 2. Api load data mhs (Pengingat Kelas)
    response = client.get("/mahasiswa/pengingat", headers=auth_headers)
    assert response.status_code == 200
    reminder = response.json()
    assert "courseName" in reminder
    assert "time" in reminder
    assert "room" in reminder


def test_crud_mahasiswa(client: TestClient) -> None:
    # 3. CRUD: CREATE Mahasiswa
    create_res = client.post(
        "/mahasiswa",
        json={
            "nim": "24999999",
            "nama_lengkap": "Budi Testing",
            "email": "budi.test@polinema.ac.id",
            "no_hp": "081234567899",
            "kelas": "TI-3A",
            "prodi": "D4-TI",
            "password": "password123",
        },
    )
    assert create_res.status_code == 201

    # Conflict on duplicate NIM
    dup_res = client.post(
        "/mahasiswa",
        json={
            "nim": "24999999",
            "nama_lengkap": "Budi Duplikat",
            "email": "budi.dup@polinema.ac.id",
        },
    )
    assert dup_res.status_code == 409

    # 3. CRUD: READ List Mahasiswa
    list_res = client.get("/mahasiswa?search=Budi")
    assert list_res.status_code == 200
    assert any(m["nim"] == "24999999" for m in list_res.json())

    # 3. CRUD: READ Detail Mahasiswa by NIM
    detail_res = client.get("/mahasiswa/24999999")
    assert detail_res.status_code == 200
    assert detail_res.json()["nama_lengkap"] == "Budi Testing"

    # 3. CRUD: UPDATE Mahasiswa
    update_res = client.put(
        "/mahasiswa/24999999",
        json={"nama_lengkap": "Budi Updated", "no_hp": "08999999999"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["data"]["nama_lengkap"] == "Budi Updated"

    # 3. CRUD: DELETE Mahasiswa
    del_res = client.delete("/mahasiswa/24999999")
    assert del_res.status_code == 200

    # Ensure deleted
    check_res = client.get("/mahasiswa/24999999")
    assert check_res.status_code == 404


def test_crud_pengajuan_ketidakhadiran(client: TestClient, auth_headers: dict) -> None:
    # 3. CRUD: CREATE Pengajuan Surat (Izin)
    post_res = client.post(
        "/mahasiswa/pengajuan",
        headers=auth_headers,
        json={
            "jenis": "izin",
            "alasan": "Mengikuti seminar teknologi",
            "matakuliah": "Pemrograman Web",
            "tanggal": "2026-11-10",
            "dokumen_path": "seminar.pdf",
        },
    )
    assert post_res.status_code == 201
    pengajuan_id = post_res.json()["data"]["id"]

    # 3. CRUD: READ List Pengajuan
    list_res = client.get("/mahasiswa/pengajuan/list", headers=auth_headers)
    assert list_res.status_code == 200
    assert any(p["id"] == pengajuan_id for p in list_res.json())

    # 3. CRUD: READ Detail
    detail_res = client.get(f"/mahasiswa/pengajuan/{pengajuan_id}", headers=auth_headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["alasan"] == "Mengikuti seminar teknologi"

    # 3. CRUD: UPDATE Pengajuan
    update_res = client.put(
        f"/mahasiswa/pengajuan/{pengajuan_id}",
        headers=auth_headers,
        json={"alasan": "Mengikuti workshop teknologi terkini"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["data"]["alasan"] == "Mengikuti workshop teknologi terkini"

    # 3. CRUD: DELETE / Batalkan Pengajuan
    del_res = client.delete(f"/mahasiswa/pengajuan/{pengajuan_id}", headers=auth_headers)
    assert del_res.status_code == 200

    # Verify deleted
    not_found_res = client.get(f"/mahasiswa/pengajuan/{pengajuan_id}", headers=auth_headers)
    assert not_found_res.status_code == 404

