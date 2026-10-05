"""Text extraction for POST /extract (SPEC.md, part A).

The rest of the pipeline only sees `Extraction.text`; it must not know which extractor ran.
Which one runs is a backend setting, never chosen by the client:

    BRIEFKLAR_EXTRACTOR=claude   fast lane: Claude vision (raw image leaves the device, MUSTER letters only)
    BRIEFKLAR_EXTRACTOR=local    on-device OCR with GLM-OCR (ocr.py)

Uploads are processed in memory only and their content is never logged.
"""

from __future__ import annotations

import base64
import io
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Protocol

from PIL import Image, ImageOps, UnidentifiedImageError

EXTRACTOR = os.getenv("BRIEFKLAR_EXTRACTOR", "claude")
CLAUDE_MODEL = os.getenv("BRIEFKLAR_CLAUDE_MODEL", "claude-sonnet-5-5")

MAX_PAGES = 10
PDF_RENDER_DPI = 200
CLAUDE_MAX_IMAGE_SIDE = 2000  # keeps photos well under Claude's per-image size limit
MIN_TEXT_CHARS = 20  # less than this is treated as "nothing readable"

SUPPORTED_MIME = {"image/jpeg", "image/png", "image/heic", "image/heif", "application/pdf"}


class ExtractionError(Exception):
    status = 500
    code = "internal_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class BadRequest(ExtractionError):
    status = 400
    code = "bad_request"


class Unreadable(ExtractionError):
    status = 422
    code = "unreadable"


class UpstreamError(ExtractionError):
    status = 502
    code = "upstream_error"


@dataclass
class Extraction:
    text: str
    pages: int
    warnings: list[str] = field(default_factory=list)


class TextExtractor(Protocol):
    def extract(self, file: bytes, mime: str) -> Extraction: ...


# --- file handling -------------------------------------------------------------------


def sniff_mime(file: bytes, declared: str | None) -> str:
    """Trust magic bytes over the declared type (phones often send HEIC as octet-stream)."""
    if file.startswith(b"%PDF"):
        return "application/pdf"
    if file.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if file.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if file[4:8] == b"ftyp" and file[8:12] in {b"heic", b"heix", b"heim", b"heis", b"mif1", b"msf1", b"hevc"}:
        return "image/heic"
    return (declared or "application/octet-stream").split(";")[0].strip().lower()


def check_supported(mime: str) -> None:
    if mime not in SUPPORTED_MIME:
        raise BadRequest("Unsupported file type. Please upload a JPEG, PNG, HEIC or PDF.")


def _open_image(file: bytes) -> Image.Image:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    try:
        image = Image.open(io.BytesIO(file))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise BadRequest("The image could not be opened.") from exc
    # Phone photos are often stored sideways with an EXIF rotation flag.
    return ImageOps.exif_transpose(image).convert("RGB")


def _pdf_page_count(file: bytes) -> int:
    import pypdfium2 as pdfium

    try:
        return len(pdfium.PdfDocument(file))
    except pdfium.PdfiumError as exc:
        raise BadRequest("The PDF could not be opened.") from exc


def _render_pdf(file: bytes, max_pages: int) -> list[Image.Image]:
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(file)
    except pdfium.PdfiumError as exc:
        raise BadRequest("The PDF could not be opened.") from exc
    return [
        pdf[i].render(scale=PDF_RENDER_DPI / 72).to_pil().convert("RGB")
        for i in range(min(len(pdf), max_pages))
    ]


def load_pages(file: bytes, mime: str) -> tuple[list[Image.Image], int]:
    """Return (page images up to MAX_PAGES, total page count)."""
    if mime == "application/pdf":
        return _render_pdf(file, MAX_PAGES), _pdf_page_count(file)
    return [_open_image(file)], 1


def _page_limit_warning(total: int) -> list[str]:
    return [f"Only the first {MAX_PAGES} of {total} pages were read."] if total > MAX_PAGES else []


def _finish(pages_text: list[str], total_pages: int, warnings: list[str]) -> Extraction:
    text = "\n\n".join(t for t in pages_text if t).strip()
    if len(re.sub(r"\s", "", text)) < MIN_TEXT_CHARS:
        raise Unreadable("Please take a sharper photo with the whole page visible.")
    return Extraction(text=text, pages=total_pages, warnings=warnings)


# --- local OCR -----------------------------------------------------------------------


def markdown_to_plain(text: str) -> str:
    """GLM-OCR answers in Markdown/HTML; /extract promises plain verbatim text."""
    text = re.sub(r"</t[dh]>\s*", "  ", text)
    text = re.sub(r"</tr>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"^[ \t]*\|?[ \t]*:?-{3,}[-|: ]*$\n?", "", text, flags=re.MULTILINE)  # table rules
    text = re.sub(r"^[ \t]*\|[ \t]?|[ \t]?\|[ \t]*$", "", text, flags=re.MULTILINE)  # outer table pipes
    text = re.sub(r"\s\|\s", "  ", text)  # inner table pipes
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)  # bold
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # headings
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


class LocalOcrExtractor:
    """On-device OCR with GLM-OCR via MLX. Nothing leaves the machine."""

    def __init__(self, model_id: str | None = None):
        from ocr import DEFAULT_MODEL

        self.model_id = model_id or DEFAULT_MODEL

    def warm_up(self) -> None:
        from ocr import preload

        preload(self.model_id)

    def extract(self, file: bytes, mime: str) -> Extraction:
        from ocr import ocr_pil

        check_supported(mime)
        images, total = load_pages(file, mime)
        warnings = _page_limit_warning(total)
        texts = []
        for number, image in enumerate(images, start=1):
            result = ocr_pil(image, model_id=self.model_id)
            text = markdown_to_plain(result.text)
            if result.truncated:
                warnings.append(f"Page {number} is very long; the end may be missing.")
            if not text and len(images) > 1:
                warnings.append(f"Page {number}: no text found.")
            texts.append(text)
        return _finish(texts, total, warnings)


# --- Claude vision (fast lane) -------------------------------------------------------

TRANSCRIBE_PROMPT = """\
Transcribe this German letter verbatim, as plain text.

- Copy every word, number, date, amount, reference number and § citation exactly as printed, \
including the letterhead, address block, reference/date block and footer. Keep umlauts, ß and \
special characters (e.g. ı, „ “) as they appear.
- Keep the reading order: letterhead, address and reference block, subject, body, closing, footer.
- One line per printed line or table row; put a blank line between paragraphs. No Markdown.
- Ignore watermarks (e.g. a large diagonal "MUSTER").
- Do not translate, summarise, correct or explain anything.
- Write [unleserlich] for any part you cannot read.
- If the image contains no readable letter text, answer exactly: NO_TEXT"""

UNREADABLE_MARK = "[unleserlich]"


def _jpeg_block(image: Image.Image) -> dict:
    image = image.copy()
    image.thumbnail((CLAUDE_MAX_IMAGE_SIDE, CLAUDE_MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    data = base64.standard_b64encode(buffer.getvalue()).decode("ascii")
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}


def _pdf_block(file: bytes) -> dict:
    data = base64.standard_b64encode(file).decode("ascii")
    return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}}


class ClaudeVisionExtractor:
    """Fast lane: Claude transcribes the raw image. Not private, so use MUSTER letters only."""

    def __init__(self, client=None, model: str = CLAUDE_MODEL):
        self._client = client
        self.model = model

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def warm_up(self) -> None:
        pass

    def extract(self, file: bytes, mime: str) -> Extraction:
        import anthropic

        check_supported(mime)
        if mime == "application/pdf":
            total = _pdf_page_count(file)
            blocks = [_pdf_block(file)]
        else:
            total = 1
            blocks = [_jpeg_block(_open_image(file))]

        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": [*blocks, {"type": "text", "text": TRANSCRIBE_PROMPT}]}],
            )
        except anthropic.BadRequestError as exc:
            raise BadRequest("The file could not be processed.") from exc
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            raise UpstreamError("Text extraction failed, please retry.") from exc

        if response.stop_reason == "refusal":
            raise UpstreamError("Text extraction failed, please retry.")
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if text == "NO_TEXT":
            text = ""

        warnings = []
        if response.stop_reason == "max_tokens":
            warnings.append("The letter is very long; the end may be missing.")
        if UNREADABLE_MARK in text:
            warnings.append(f"Some parts could not be read and are marked {UNREADABLE_MARK}.")
        return _finish([text], total, warnings)


@lru_cache(maxsize=1)
def get_extractor() -> TextExtractor:
    if EXTRACTOR == "local":
        return LocalOcrExtractor()
    if EXTRACTOR == "claude":
        return ClaudeVisionExtractor()
    raise RuntimeError(f"BRIEFKLAR_EXTRACTOR must be 'claude' or 'local', got {EXTRACTOR!r}")
