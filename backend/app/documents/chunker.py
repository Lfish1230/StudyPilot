from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import tiktoken

from app.documents.parser import PdfPage


class Tokenizer(Protocol):
    def encode(self, text: str) -> list[int]: ...

    def decode(self, tokens: list[int]) -> str: ...


@dataclass(frozen=True, slots=True)
class TextChunk:
    page_number: int
    content: str
    token_count: int


@lru_cache
def default_tokenizer() -> Tokenizer:
    return tiktoken.get_encoding("cl100k_base")


def chunk_pages(
    pages: list[PdfPage],
    tokenizer: Tokenizer | None = None,
    max_tokens: int = 700,
    overlap_tokens: int = 100,
) -> list[TextChunk]:
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    if overlap_tokens < 0 or overlap_tokens >= max_tokens:
        raise ValueError("overlap_tokens must be between 0 and max_tokens")

    active_tokenizer = tokenizer or default_tokenizer()
    step = max_tokens - overlap_tokens
    chunks: list[TextChunk] = []
    for page in pages:
        tokens = active_tokenizer.encode(page.text)
        for start in range(0, len(tokens), step):
            chunk_tokens = tokens[start : start + max_tokens]
            if not chunk_tokens:
                break
            content = active_tokenizer.decode(chunk_tokens)
            if content.strip():
                chunks.append(
                    TextChunk(
                        page_number=page.page_number,
                        content=content,
                        token_count=len(chunk_tokens),
                    )
                )
            if start + max_tokens >= len(tokens):
                break
    return chunks
