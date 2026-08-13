import asyncio
from typing import Never, Protocol

from supabase import Client, create_client

from app.core.config import Settings
from app.core.errors import ServiceUnavailableError


class ObjectStorage(Protocol):
    async def upload(self, object_key: str, data: bytes, content_type: str) -> None: ...

    async def download(self, object_key: str) -> bytes: ...

    async def delete(self, object_key: str) -> None: ...


class FakeObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def upload(self, object_key: str, data: bytes, content_type: str) -> None:
        self.objects[object_key] = (data, content_type)

    async def download(self, object_key: str) -> bytes:
        try:
            return self.objects[object_key][0]
        except KeyError as exc:
            raise ServiceUnavailableError(
                "storage_unavailable", "文件存储暂时不可用，请稍后重试。"
            ) from exc

    async def delete(self, object_key: str) -> None:
        self.objects.pop(object_key, None)


class UnconfiguredObjectStorage:
    async def upload(self, object_key: str, data: bytes, content_type: str) -> None:
        del object_key, data, content_type
        self._raise_unavailable()

    async def download(self, object_key: str) -> bytes:
        del object_key
        self._raise_unavailable()

    async def delete(self, object_key: str) -> None:
        del object_key
        self._raise_unavailable()

    @staticmethod
    def _raise_unavailable() -> Never:
        raise ServiceUnavailableError(
            "storage_unavailable", "文件存储尚未配置，请联系管理员。"
        )


class SupabaseObjectStorage:
    def __init__(self, client: Client, bucket: str) -> None:
        self._bucket = client.storage.from_(bucket)

    async def upload(self, object_key: str, data: bytes, content_type: str) -> None:
        try:
            await asyncio.to_thread(
                self._bucket.upload,
                object_key,
                data,
                {"content-type": content_type, "upsert": "false"},
            )
        except Exception as exc:
            raise self._unavailable() from exc

    async def download(self, object_key: str) -> bytes:
        try:
            return await asyncio.to_thread(self._bucket.download, object_key)
        except Exception as exc:
            raise self._unavailable() from exc

    async def delete(self, object_key: str) -> None:
        try:
            await asyncio.to_thread(self._bucket.remove, [object_key])
        except Exception as exc:
            raise self._unavailable() from exc

    @staticmethod
    def _unavailable() -> ServiceUnavailableError:
        return ServiceUnavailableError(
            "storage_unavailable", "文件存储暂时不可用，请稍后重试。"
        )


def create_object_storage(settings: Settings) -> ObjectStorage:
    if not settings.supabase_url or not settings.supabase_service_key:
        return UnconfiguredObjectStorage()
    client = create_client(settings.supabase_url, settings.supabase_service_key)
    return SupabaseObjectStorage(client, settings.supabase_storage_bucket)
