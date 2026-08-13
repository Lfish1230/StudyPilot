import asyncio
from collections.abc import Callable
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import update

from app.core.database import SessionLocal
from app.core.errors import ServiceUnavailableError
from app.documents.model import Document, DocumentStatus
from app.documents.storage import FakeObjectStorage
from tests.conftest import CreatedUser

PDF_BYTES = b"%PDF-1.4\n%%EOF"


def create_course(
    client: TestClient, headers: dict[str, str], name: str = "机器学习"
) -> str:
    response = client.post("/courses", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


def upload_pdf(
    client: TestClient,
    course_id: str,
    headers: dict[str, str],
    filename: str = "lecture.pdf",
    data: bytes = PDF_BYTES,
    content_type: str = "application/pdf",
):
    return client.post(
        f"/courses/{course_id}/documents",
        headers=headers,
        files={"file": (filename, data, content_type)},
    )


def test_valid_pdf_is_stored_with_private_generated_key(
    client: TestClient,
    auth_headers: dict[str, str],
    object_storage: FakeObjectStorage,
    scheduled_document_ids: list[str],
) -> None:
    course_id = create_course(client, auth_headers)
    response = upload_pdf(
        client,
        course_id,
        auth_headers,
        filename="../../private lecture.pdf",
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "uploaded"
    assert payload["original_name"] == "../../private lecture.pdf"
    assert payload["size_bytes"] == len(PDF_BYTES)
    assert payload["id"] in scheduled_document_ids

    [object_key] = object_storage.objects
    owner_id = object_key.split("/")[0]
    assert object_key == f"{owner_id}/{course_id}/{payload['id']}.pdf"
    assert "private lecture" not in object_key
    assert object_storage.objects[object_key] == (PDF_BYTES, "application/pdf")


def test_pdf_validation_rejects_oversize_mime_and_magic_bytes(
    client: TestClient, auth_headers: dict[str, str], object_storage: FakeObjectStorage
) -> None:
    course_id = create_course(client, auth_headers)
    cases = [
        (
            b"%PDF-" + b"x" * (20 * 1024 * 1024 - 4),
            "application/pdf",
            413,
            "pdf_too_large",
        ),
        (PDF_BYTES, "text/plain", 415, "invalid_pdf_type"),
        (b"not a pdf", "application/pdf", 422, "invalid_pdf_content"),
    ]
    for data, content_type, status_code, code in cases:
        response = upload_pdf(
            client,
            course_id,
            auth_headers,
            data=data,
            content_type=content_type,
        )
        assert response.status_code == status_code
        assert response.json()["code"] == code
        assert response.json()["request_id"]
    assert object_storage.objects == {}


def test_document_routes_are_owner_scoped_and_delete_storage(
    client: TestClient,
    user_factory: Callable[..., CreatedUser],
    token_for: Callable[[CreatedUser], dict[str, str]],
    object_storage: FakeObjectStorage,
) -> None:
    alice, bob = user_factory(), user_factory()
    alice_headers, bob_headers = token_for(alice), token_for(bob)
    course_id = create_course(client, alice_headers)
    response = upload_pdf(client, course_id, alice_headers)
    document_id = response.json()["id"]

    own_get = client.get(f"/documents/{document_id}", headers=alice_headers)
    foreign_get = client.get(f"/documents/{document_id}", headers=bob_headers)
    foreign_list = client.get(f"/courses/{course_id}/documents", headers=bob_headers)
    assert own_get.status_code == 200
    assert foreign_get.status_code == 404
    assert foreign_list.status_code == 404

    listed = client.get(f"/courses/{course_id}/documents", headers=alice_headers)
    assert [item["id"] for item in listed.json()] == [document_id]
    deleted = client.delete(f"/documents/{document_id}", headers=alice_headers)
    assert deleted.status_code == 204
    assert object_storage.objects == {}
    missing = client.get(f"/documents/{document_id}", headers=alice_headers)
    assert missing.status_code == 404


def test_foreign_course_upload_does_not_store_file(
    client: TestClient,
    user_factory: Callable[..., CreatedUser],
    token_for: Callable[[CreatedUser], dict[str, str]],
    object_storage: FakeObjectStorage,
) -> None:
    alice, bob = user_factory(), user_factory()
    course_id = create_course(client, token_for(alice))
    response = upload_pdf(client, course_id, token_for(bob))
    assert response.status_code == 404
    assert response.json()["code"] == "course_not_found"
    assert object_storage.objects == {}


def test_daily_upload_quota_is_five(
    client: TestClient,
    auth_headers: dict[str, str],
    object_storage: FakeObjectStorage,
) -> None:
    course_id = create_course(client, auth_headers)
    for index in range(5):
        response = upload_pdf(
            client, course_id, auth_headers, filename=f"lecture-{index}.pdf"
        )
        assert response.status_code == 201

    blocked = upload_pdf(client, course_id, auth_headers, filename="sixth.pdf")
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "upload_quota_exceeded"
    assert len(object_storage.objects) == 5


def test_retry_requires_failed_status_and_schedules_again(
    client: TestClient,
    auth_headers: dict[str, str],
    scheduled_document_ids: list[str],
) -> None:
    course_id = create_course(client, auth_headers)
    uploaded = upload_pdf(client, course_id, auth_headers).json()
    document_id = uploaded["id"]

    not_failed = client.post(f"/documents/{document_id}/retry", headers=auth_headers)
    assert not_failed.status_code == 409
    assert not_failed.json()["code"] == "document_not_failed"

    async def mark_failed() -> None:
        async with SessionLocal() as session:
            await session.execute(
                update(Document)
                .where(Document.id == UUID(document_id))
                .values(
                    status=DocumentStatus.FAILED,
                    failure_code="embedding_unavailable",
                    failure_message="temporary failure",
                )
            )
            await session.commit()

    asyncio.run(mark_failed())
    retried = client.post(f"/documents/{document_id}/retry", headers=auth_headers)
    assert retried.status_code == 200
    assert retried.json()["status"] == "uploaded"
    assert retried.json()["failure_code"] is None
    assert scheduled_document_ids.count(document_id) == 2


class DeleteFailingStorage(FakeObjectStorage):
    async def delete(self, object_key: str) -> None:
        del object_key
        raise ServiceUnavailableError(
            "storage_unavailable", "文件存储暂时不可用，请稍后重试。"
        )


def test_storage_delete_failure_keeps_document_metadata(
    client: TestClient,
    auth_headers: dict[str, str],
    object_storage: FakeObjectStorage,
) -> None:
    course_id = create_course(client, auth_headers)
    document_id = upload_pdf(client, course_id, auth_headers).json()["id"]
    client.app.state.object_storage = DeleteFailingStorage()

    failed = client.delete(f"/documents/{document_id}", headers=auth_headers)
    assert failed.status_code == 503
    assert failed.json()["code"] == "storage_unavailable"

    still_exists = client.get(f"/documents/{document_id}", headers=auth_headers)
    assert still_exists.status_code == 200
    assert object_storage.objects
