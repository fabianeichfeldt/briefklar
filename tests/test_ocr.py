"""Smoke test: the default OCR model finds every key field in the sample letters."""

import json
from pathlib import Path

import pytest

from ocr import DEFAULT_MODEL, ocr_image

ROOT = Path(__file__).resolve().parent.parent
KEY_FIELDS = json.loads((ROOT / "tests" / "key_fields.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("doc", sorted(KEY_FIELDS))
def test_key_fields_recognised(doc):
    result = ocr_image(ROOT / "samples" / f"{doc}.png")
    text = " ".join(result.text.replace("*", "").split())
    missing = [field for field in KEY_FIELDS[doc] if field not in text]
    assert not missing, f"{DEFAULT_MODEL} missed {missing} in {doc}"


def test_model_loaded_on_one_thread_works_from_another():
    """FastAPI loads the model at startup and serves requests from a thread pool."""
    from concurrent.futures import ThreadPoolExecutor

    from ocr import preload

    preload()
    with ThreadPoolExecutor(max_workers=2) as pool:
        texts = list(pool.map(lambda d: ocr_image(ROOT / "samples" / f"{d}.png").text, ["doc_3", "doc_4"]))
    assert "30.10.2026" in texts[0] and "55,08 Euro" in texts[1]
