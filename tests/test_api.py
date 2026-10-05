"""POST /extract against the openapi.yaml contract."""

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import api
from extractors import ClaudeVisionExtractor, Extraction, LocalOcrExtractor, Unreadable, markdown_to_plain

ROOT = Path(__file__).resolve().parent.parent
KEY_FIELDS = json.loads((ROOT / "tests" / "key_fields.json").read_text(encoding="utf-8"))
client = TestClient(api.app)


def use_extractor(monkeypatch, extractor):
    monkeypatch.setattr(api, "get_extractor", lambda: extractor)


def post(data: bytes, filename="letter.png", mime="image/png"):
    return client.post("/extract", files={"file": (filename, data, mime)})


def sample_bytes(doc: str, fmt: str) -> bytes:
    image = Image.open(ROOT / "samples" / f"{doc}.png").convert("RGB")
    if fmt == "HEIF":
        from pillow_heif import register_heif_opener

        register_heif_opener()
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


class FakeExtractor:
    def __init__(self, text="Sehr geehrte Frau Muster, Ihr Termin ist am 20.10.2026."):
        self.text = text
        self.calls = []

    def extract(self, file, mime):
        self.calls.append(mime)
        if not self.text:
            raise Unreadable("Please take a sharper photo with the whole page visible.")
        return Extraction(text=self.text, pages=1, warnings=[])


# --- contract & errors (fast) ----------------------------------------------------------


def test_returns_extract_response(monkeypatch):
    use_extractor(monkeypatch, FakeExtractor())
    response = post((ROOT / "samples" / "doc_1.png").read_bytes())
    assert response.status_code == 200
    assert response.json() == {
        "text": "Sehr geehrte Frau Muster, Ihr Termin ist am 20.10.2026.",
        "pages": 1,
        "warnings": [],
    }


def test_mime_is_sniffed_not_trusted(monkeypatch):
    fake = FakeExtractor()
    use_extractor(monkeypatch, fake)
    post((ROOT / "samples" / "doc_1.png").read_bytes(), filename="IMG_0001", mime="application/octet-stream")
    assert fake.calls == ["image/png"]


def test_missing_file_is_400():
    response = client.post("/extract")
    assert response.status_code == 400
    assert response.json()["code"] == "bad_request"


def test_unsupported_type_is_400():
    response = post(b"just some text", filename="letter.txt", mime="text/plain")
    assert response.status_code == 400
    assert response.json() == {
        "code": "bad_request",
        "message": "Unsupported file type. Please upload a JPEG, PNG, HEIC or PDF.",
    }


def test_corrupt_image_is_400():
    response = post(b"\x89PNG\r\n\x1a\n" + b"garbage" * 10)
    assert response.status_code == 400


def test_unreadable_is_422(monkeypatch):
    use_extractor(monkeypatch, FakeExtractor(text=""))
    response = post((ROOT / "samples" / "doc_1.png").read_bytes())
    assert response.status_code == 422
    assert response.json()["code"] == "unreadable"


def test_markdown_is_flattened_to_plain_text():
    md = "## Zahlungserinnerung\n\nBitte bis **15.10.2026** zahlen.\n\n| Zeitraum | 07.2026 |\n|---|---|\n| Betrag | **55,08 Euro** |"
    assert markdown_to_plain(md) == (
        "Zahlungserinnerung\n\nBitte bis 15.10.2026 zahlen.\n\nZeitraum  07.2026\nBetrag  55,08 Euro"
    )


def test_claude_extractor_sends_image_and_parses_text():
    sent = {}

    def create(**kwargs):
        sent.update(kwargs)
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text="Stadt Nürnberg\nTermin: Dienstag, 20.10.2026, 09:30 Uhr")],
        )

    fake_client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    result = ClaudeVisionExtractor(client=fake_client).extract(sample_bytes("doc_1", "JPEG"), "image/jpeg")

    assert result.text.endswith("20.10.2026, 09:30 Uhr") and result.pages == 1
    assert sent["model"] == "claude-sonnet-5-5"
    image_block = sent["messages"][0]["content"][0]
    assert image_block["type"] == "image" and image_block["source"]["media_type"] == "image/jpeg"


def test_claude_extractor_no_text_is_unreadable():
    reply = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="NO_TEXT")])
    fake_client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=lambda **_: reply)))
    with pytest.raises(Unreadable):
        ClaudeVisionExtractor(client=fake_client).extract(sample_bytes("doc_1", "JPEG"), "image/jpeg")


# --- local OCR end to end (runs GLM-OCR, ~5 s per page) ----------------------------------


@pytest.mark.parametrize(
    ("doc", "fmt", "filename", "mime"),
    [
        ("doc_1", "PNG", "doc_1.png", "image/png"),
        ("doc_4", "PDF", "doc_4.pdf", "application/pdf"),
        ("doc_6", "HEIF", "IMG_0042.HEIC", "image/heic"),
    ],
)
def test_local_extract_end_to_end(monkeypatch, doc, fmt, filename, mime):
    use_extractor(monkeypatch, LocalOcrExtractor())
    response = post(sample_bytes(doc, fmt), filename=filename, mime=mime)
    assert response.status_code == 200
    body = response.json()
    assert body["pages"] == 1 and body["warnings"] == []
    assert "**" not in body["text"]
    text = " ".join(body["text"].split())
    missing = [f for f in KEY_FIELDS[doc] if f not in text]
    assert not missing, missing
