from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.conftest import CreatedUser


def test_course_crud_is_owner_scoped(
    client: TestClient,
    user_factory: Callable[..., CreatedUser],
    token_for: Callable[[CreatedUser], dict[str, str]],
) -> None:
    alice, bob = user_factory(), user_factory()
    alice_headers = token_for(alice)
    bob_headers = token_for(bob)

    created = client.post(
        "/courses", json={"name": " 计算机网络 "}, headers=alice_headers
    )
    assert created.status_code == 201
    assert created.json()["name"] == "计算机网络"
    course_id = created.json()["id"]

    assert client.get(f"/courses/{course_id}", headers=alice_headers).status_code == 200
    foreign = client.get(f"/courses/{course_id}", headers=bob_headers)
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "course_not_found"

    assert (
        client.delete(f"/courses/{course_id}", headers=alice_headers).status_code == 204
    )
    assert client.get(f"/courses/{course_id}", headers=alice_headers).status_code == 404


def test_courses_are_listed_newest_first(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    first = client.post(
        "/courses", json={"name": "数据结构"}, headers=auth_headers
    ).json()
    second = client.post(
        "/courses", json={"name": "操作系统"}, headers=auth_headers
    ).json()

    response = client.get("/courses", headers=auth_headers)
    assert response.status_code == 200
    assert [course["id"] for course in response.json()] == [
        second["id"],
        first["id"],
    ]


def test_course_name_validation_uses_stable_error(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    for name in ["   ", "x" * 81]:
        response = client.post("/courses", json={"name": name}, headers=auth_headers)
        assert response.status_code == 422
        assert response.json()["code"] == "validation_error"
        assert response.json()["request_id"]


def test_courses_require_authentication(client: TestClient) -> None:
    response = client.get("/courses")
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"
