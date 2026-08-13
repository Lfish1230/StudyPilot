from typing import Any, cast

import pytest

from app.core.errors import ServiceUnavailableError
from app.documents.storage import FakeObjectStorage, SupabaseObjectStorage


@pytest.mark.asyncio
async def test_fake_storage_round_trip_and_delete() -> None:
    storage = FakeObjectStorage()
    await storage.upload("private/file.pdf", b"pdf", "application/pdf")
    assert await storage.download("private/file.pdf") == b"pdf"
    await storage.delete("private/file.pdf")
    with pytest.raises(ServiceUnavailableError) as exc_info:
        await storage.download("private/file.pdf")
    assert exc_info.value.code == "storage_unavailable"


class BrokenBucket:
    def upload(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("provider secret payload")

    def download(self, *_args: object, **_kwargs: object) -> bytes:
        raise RuntimeError("provider secret payload")

    def remove(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("provider secret payload")


class FakeStorageClient:
    def from_(self, _bucket: str) -> BrokenBucket:
        return BrokenBucket()


class FakeSupabaseClient:
    storage = FakeStorageClient()


@pytest.mark.asyncio
async def test_supabase_errors_are_sanitized() -> None:
    client = cast(Any, FakeSupabaseClient())
    storage = SupabaseObjectStorage(client, "private")
    with pytest.raises(ServiceUnavailableError) as exc_info:
        await storage.upload("file.pdf", b"pdf", "application/pdf")
    assert exc_info.value.code == "storage_unavailable"
    assert "secret" not in exc_info.value.message
