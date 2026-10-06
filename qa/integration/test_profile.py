from fastapi.testclient import TestClient


def test_profile_with_valid_token(client: TestClient, auth_headers: dict) -> None:
    response = client.get("/users/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"nim": "24000001", "name": "Demo Student One"}


def test_profile_without_token_returns_401(client: TestClient) -> None:
    response = client.get("/users/me")

    assert response.status_code == 401
