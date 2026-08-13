import pytest

from app.ai.fake import FakeChatClient, FakeEmbeddingClient
from app.core.config import Settings
from app.main import create_ai_clients


def test_fake_provider_is_available_only_in_test_environment() -> None:
    embeddings, chat = create_ai_clients(
        Settings(environment="test", ai_provider="fake", embedding_dimension=8)
    )

    assert isinstance(embeddings, FakeEmbeddingClient)
    assert isinstance(chat, FakeChatClient)


@pytest.mark.parametrize("environment", ["development", "staging", "production"])
def test_fake_provider_is_rejected_outside_test(environment: str) -> None:
    with pytest.raises(RuntimeError, match="restricted to ENVIRONMENT=test"):
        create_ai_clients(Settings(environment=environment, ai_provider="fake"))
