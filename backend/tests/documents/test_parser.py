import pymupdf
import pytest

from app.documents.parser import (
    PdfPageLimitError,
    ScannedPdfError,
    normalize_page_text,
    parse_pdf,
)


def make_pdf(page_texts: list[str | None]) -> bytes:
    document = pymupdf.open()
    for text in page_texts:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def test_parse_pdf_numbers_pages_normalizes_text_and_ignores_blank_pages() -> None:
    pages = parse_pdf(make_pdf(["alpha   beta\n\ngamma", None, "delta"]))
    assert [page.page_number for page in pages] == [1, 3]
    assert pages[0].text == "alpha beta gamma"
    assert pages[1].text == "delta"


def test_normalize_page_text_preserves_paragraph_breaks() -> None:
    assert normalize_page_text("alpha   beta\n\n gamma  delta") == (
        "alpha beta\n\ngamma delta"
    )


def test_parse_pdf_rejects_scanned_or_blank_document() -> None:
    with pytest.raises(ScannedPdfError):
        parse_pdf(make_pdf([None, "   "]))


def test_parse_pdf_rejects_page_limit_before_extraction() -> None:
    with pytest.raises(PdfPageLimitError):
        parse_pdf(make_pdf(["one", "two", "three"]), max_pages=2)
