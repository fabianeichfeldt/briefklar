"""logic.redact() on the six MUSTER letters: no personal data may reach part B (SPEC.md, part A).

Runs on the hand-made ground-truth transcriptions, which match the local OCR output closely.
"""

import re
from pathlib import Path

import pytest

import logic

ROOT = Path(__file__).resolve().parent.parent

# Personal data per letter that must not survive redaction.
PERSONAL = {
    "doc_1": ["Olena Petrenko", "Musterstraße 14", "90402 Nürnberg", "AB-2026/48213-P"],
    "doc_2": ["Ahmad Rahimi", "Beispielweg 7", "90441 Nürnberg", "24401//0098765", "512D334455"],
    "doc_3": ["Priya Natarajan", "Beispielgasse 3", "90419 Nürnberg", "241/123/45678", "12 345 678 901"],
    "doc_4": ["Carlos Mendes", "Musterallee 21", "90459 Nürnberg", "000 000 001"],
    "doc_5": ["Ji-woo Park", "Min-jun Park", "Beispielstraße 9", "90491 Nürnberg", "03.05.2024", "KITA-2026-77310"],
    "doc_6": ["Mehmet Yıldız", "Elif Yıldız", "Musterring 5", "90471 Nürnberg", "123FK456789"],
}

# Deadlines, appointments and amounts must stay readable for part B.
KEEP = {
    "doc_1": ["15.11.2026", "20.10.2026, 09:30 Uhr", "13.10.2026", "Zimmer 2.14"],
    "doc_2": ["14.10.2026 um 10:15 Uhr", "Zimmer 2.07", "10 Prozent"],
    "doc_3": ["30.10.2026", "0,25 Prozent", "25 Euro"],
    "doc_4": ["07.2026 – 09.2026", "55,08 Euro", "15.10.2026"],
    "doc_5": ["01.12.2026", "12.10.2026", "10 Tagen"],
    "doc_6": ["28.10.2026", "2026/2027"],
}

# Words that appear in the personal data but are not personal on their own.
NOT_PERSONAL = {"Nürnberg"}


def leaks(item: str, redacted: str) -> list[str]:
    """The item itself, or any distinctive piece of it, still present in the redacted text."""
    found = [item] if item in redacted else []
    for piece in re.split(r"[\s,]+", item):
        if len(piece) >= 4 and piece not in NOT_PERSONAL and re.search(rf"(?<!\w){re.escape(piece)}(?!\w)", redacted):
            found.append(piece)
    digits = re.sub(r"\D", "", item)
    if len(digits) >= 6 and digits in re.sub(r"\D", "", redacted):
        found.append(f"digits {digits}")
    return found


@pytest.mark.parametrize("doc", sorted(PERSONAL))
def test_no_personal_data_survives(doc):
    text = (ROOT / "tests" / "ground_truth" / f"{doc}.txt").read_text(encoding="utf-8")
    redacted, mapping = logic.redact(text)
    leaked = {item: found for item in PERSONAL[doc] if (found := leaks(item, redacted))}
    assert not leaked, f"{doc} leaks {leaked}"
    assert logic.restore(redacted, mapping) == text


@pytest.mark.parametrize("doc", sorted(KEEP))
def test_deadlines_and_amounts_are_kept(doc):
    text = (ROOT / "tests" / "ground_truth" / f"{doc}.txt").read_text(encoding="utf-8")
    redacted, _ = logic.redact(text)
    lost = [k for k in KEEP[doc] if k not in redacted]
    assert not lost, f"{doc} lost {lost}"


@pytest.mark.parametrize("doc", sorted(PERSONAL))
def test_no_personal_data_survives_local_ocr(doc):
    """Same check on what the app really redacts: GLM-OCR output (~5 s per letter)."""
    from extractors import LocalOcrExtractor

    text = LocalOcrExtractor().extract((ROOT / "samples" / f"{doc}.png").read_bytes(), "image/png").text
    redacted, _ = logic.redact(text)
    leaked = {item: found for item in PERSONAL[doc] if (found := leaks(item, redacted))}
    assert not leaked, f"{doc} leaks {leaked}"
    lost = [k for k in KEEP[doc] if k not in redacted]
    assert not lost, f"{doc} lost {lost}"
