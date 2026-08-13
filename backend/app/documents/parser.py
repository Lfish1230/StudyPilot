import re
from dataclasses import dataclass
from typing import Any

import pymupdf


@dataclass(frozen=True, slots=True)
class PdfPage:
    page_number: int
    text: str


class PdfParsingError(Exception):
    """Base exception for safe, expected PDF parsing failures."""


class InvalidPdfError(PdfParsingError):
    pass


class PdfPageLimitError(PdfParsingError):
    pass


class ScannedPdfError(PdfParsingError):
    pass


def normalize_page_text(text: str) -> str:
    normalized_lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    paragraphs: list[str] = []
    current: list[str] = []
    for line in normalized_lines:
        if line:
            current.append(line)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def parse_pdf(data: bytes, max_pages: int = 300) -> list[PdfPage]:
    try:
        document: Any = pymupdf.open(  # type: ignore[no-untyped-call]
            stream=data, filetype="pdf"
        )
    except Exception as exc:
        raise InvalidPdfError("PDF 内容无法解析。") from exc

    try:
        if document.page_count > max_pages:
            raise PdfPageLimitError(f"PDF 页数不能超过 {max_pages} 页。")
        pages = [
            PdfPage(index + 1, normalized)
            for index, page in enumerate(document)
            if (normalized := normalize_page_text(page.get_text("text")))
        ]
    finally:
        document.close()

    if not pages:
        raise ScannedPdfError("PDF 没有可提取的文字。")
    return pages
