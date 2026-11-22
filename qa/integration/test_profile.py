"""Integration tests for student profile view/update and strict JWT verification."""

from fastapi.testclient import TestClient


def test_get_profile_authenticated(
    client: TestClient,
    seeded_auth_headers: dict[str, str],
) -> None:
    response = client.get("/users/me", headers=seeded_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["nim"] == "24000001"
    assert data["name"] == "Demo Student One"
    assert data["fullName"] == "Demo Student One"
    assert data["className"] == "TI-3A"
    assert data["prodi_kode"] == "D4-TI"


def test_get_profile_unauthenticated(client: TestClient) -> None:
    response = client.get("/users/me")
    assert response.status_code == 401


def test_forged_jwt_prefix_rejected(client: TestClient) -> None:
    # Legacy prototype accepted fake `jwt_<nim>` tokens; must now strictly fail with 401.
    response = client.get(
        "/users/me",
        headers={"Authorization": "Bearer jwt_24000001"},
    )
    assert response.status_code == 401


def test_update_profile_me_persists(
    client: TestClient,
    temp_student: dict[str, object],
) -> None:
    headers = temp_student["headers"]
    nim = str(temp_student["nim"])

    update_resp = client.put(
        "/mahasiswa/me",
        json={
            "fullName": "Updated Name Flutter",
            "phoneNumber": "081234567899",
            "className": "TI-3B",
        },
        headers=headers,  # type: ignore[arg-type]
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()["data"]
    assert updated["nama_lengkap"] == "Updated Name Flutter"
    assert updated["fullName"] == "Updated Name Flutter"
    assert updated["no_hp"] == "081234567899"
    assert updated["kelas"] == "TI-3B"

    # Re-fetch from DB to ensure changes persisted across requests.
    me_resp = client.get("/mahasiswa/me", headers=headers)  # type: ignore[arg-type]
    assert me_resp.status_code == 200
    assert me_resp.json()["nim"] == nim
    assert me_resp.json()["nama_lengkap"] == "Updated Name Flutter"
    assert me_resp.json()["kelas"] == "TI-3B"
