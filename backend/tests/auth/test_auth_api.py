from fastapi.testclient import TestClient


def test_register_login_and_me(client: TestClient) -> None:
    registered = client.post(
        "/auth/register",
        json={"email": " Student@Example.com ", "password": "correct-horse-42"},
    )
    assert registered.status_code == 201
    assert registered.json()["email"] == "student@example.com"
    assert "password" not in registered.text

    login = client.post(
        "/auth/login",
        json={"email": "student@example.com", "password": "correct-horse-42"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "student@example.com"


def test_duplicate_email_uses_stable_error_shape(client: TestClient) -> None:
    payload = {"email": "same@example.com", "password": "correct-horse-42"}
    assert client.post("/auth/register", json=payload).status_code == 201
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 409
    assert response.json()["code"] == "email_already_registered"
    assert response.json()["request_id"]


def test_invalid_credentials_do_not_reveal_if_email_exists(
    client: TestClient,
) -> None:
    client.post(
        "/auth/register",
        json={"email": "known@example.com", "password": "correct-horse-42"},
    )
    responses = [
        client.post(
            "/auth/login",
            json={"email": "known@example.com", "password": "wrong-password"},
        ),
        client.post(
            "/auth/login",
            json={"email": "unknown@example.com", "password": "wrong-password"},
        ),
    ]
    assert [response.status_code for response in responses] == [401, 401]
    assert [response.json()["code"] for response in responses] == [
        "invalid_credentials",
        "invalid_credentials",
    ]


def test_short_password_and_missing_token_use_stable_errors(
    client: TestClient,
) -> None:
    invalid = client.post(
        "/auth/register",
        json={"email": "student@example.com", "password": "short"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "validation_error"
    assert invalid.json()["request_id"]

    unauthenticated = client.get("/auth/me")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == "not_authenticated"
