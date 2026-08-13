import tiktoken

from app.documents.chunker import chunk_pages
from app.documents.parser import PdfPage


def test_chunks_never_cross_page_boundaries_or_token_limit() -> None:
    tokenizer = tiktoken.get_encoding("cl100k_base")
    pages = [PdfPage(1, "alpha " * 800), PdfPage(2, "beta " * 800)]
    chunks = chunk_pages(pages, tokenizer, max_tokens=700, overlap_tokens=100)
    assert {chunk.page_number for chunk in chunks} == {1, 2}
    assert all(chunk.token_count <= 700 for chunk in chunks)
    assert all(
        not ("alpha" in chunk.content and "beta" in chunk.content) for chunk in chunks
    )


def test_chunks_have_deterministic_token_overlap() -> None:
    tokenizer = tiktoken.get_encoding("cl100k_base")
    [first, second] = chunk_pages(
        [PdfPage(1, "token " * 1000)],
        tokenizer,
        max_tokens=700,
        overlap_tokens=100,
    )
    first_tokens = tokenizer.encode(first.content)
    second_tokens = tokenizer.encode(second.content)
    assert first_tokens[-100:] == second_tokens[:100]


def test_short_page_produces_one_chunk() -> None:
    chunks = chunk_pages([PdfPage(4, "short content")])
    assert len(chunks) == 1
    assert chunks[0].page_number == 4
    assert chunks[0].content == "short content"
