"""Bake-off: compare OCR engines against hand-transcribed ground truth.

    uv run scripts/eval_ocr.py [--models ...] [--tesseract/--no-tesseract]

Metrics per engine:
  CER       character error rate vs. tests/ground_truth/<doc>.txt, after normalising
            whitespace, Markdown/HTML markup and bullet glyphs (layout differences are not errors)
  word acc  order-independent: share of reference words reproduced exactly (multiset overlap),
            so it penalises dropped or misread words but not a different reading order
  key hits  share of must-find strings (dates, IDs, amounts, names) from tests/key_fields.json
"""

import argparse
import gc
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

from rapidfuzz.distance import Levenshtein

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # ocr.py lives in the repo root

from ocr import ocr_image

DOCS = ROOT / "samples"
GROUND_TRUTH = ROOT / "tests" / "ground_truth"
KEY_FIELDS = json.loads((ROOT / "tests" / "key_fields.json").read_text(encoding="utf-8"))
RAW_OUT = ROOT / "output" / "eval"

DEFAULT_MODELS = [
    "mlx-community/GLM-OCR-bf16",
    "mlx-community/GLM-OCR-8bit",
    "mlx-community/PaddleOCR-VL-1.6-4bit",
    "mlx-community/dots.ocr-4bit",
]


def normalise(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)  # HTML tables / tags
    text = re.sub(r"^\s*\|?\s*:?-{3,}.*$", " ", text, flags=re.MULTILINE)  # Markdown table rules
    text = re.sub(r"[*_#|`]", " ", text)  # Markdown emphasis, headings, table pipes
    text = re.sub(r"^\s*[•·\-–]\s+", "", text, flags=re.MULTILINE)  # list bullets
    text = text.replace("•", "·").replace(" ", " ")
    return " ".join(text.split())


def cer(prediction: str, reference: str) -> float:
    return Levenshtein.distance(normalise(prediction), normalise(reference)) / len(normalise(reference))


def word_accuracy(prediction: str, reference: str) -> float:
    ref, hyp = Counter(normalise(reference).split()), Counter(normalise(prediction).split())
    return sum((ref & hyp).values()) / sum(ref.values())


def key_hits(doc: str, text: str) -> tuple[int, int, list[str]]:
    flat = normalise(text)
    missing = [k for k in KEY_FIELDS[doc] if k not in flat]
    return len(KEY_FIELDS[doc]) - len(missing), len(KEY_FIELDS[doc]), missing


def run_tesseract(path: Path) -> tuple[str, float]:
    import pytesseract

    start = time.perf_counter()
    text = pytesseract.image_to_string(str(path), lang="deu")
    return text, time.perf_counter() - start


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    parser.add_argument("--tesseract", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    images = sorted(DOCS.glob("doc_*.png"))
    engines = (["tesseract-deu"] if args.tesseract else []) + args.models
    rows = []
    for engine in engines:
        out_dir = RAW_OUT / engine.split("/")[-1]
        out_dir.mkdir(parents=True, exist_ok=True)
        cers, accs, secs, hits, total = [], [], [], 0, 0
        for image in images:
            if engine == "tesseract-deu":
                text, seconds = run_tesseract(image)
            else:
                result = ocr_image(image, model_id=engine)
                text, seconds = result.text, result.seconds
            (out_dir / f"{image.stem}.md").write_text(text, encoding="utf-8")
            reference = (GROUND_TRUTH / f"{image.stem}.txt").read_text(encoding="utf-8")
            c = cer(text, reference)
            a = word_accuracy(text, reference)
            accs.append(a)
            h, n, missing = key_hits(image.stem, text)
            cers.append(c)
            secs.append(seconds)
            hits += h
            total += n
            print(f"  {engine:<38} {image.stem}  CER {c:6.2%}  words {a:6.2%}  keys {h}/{n}  {seconds:5.1f}s"
                  + (f"  missing: {missing}" if missing else ""))
        rows.append((engine, sum(cers) / len(cers), sum(accs) / len(accs), hits, total, sum(secs) / len(secs)))
        gc.collect()

    print("\n| Engine | word acc | mean CER | key fields | sec/page |\n|---|---|---|---|---|")
    for engine, mean_cer, mean_acc, hits, total, sec in sorted(rows, key=lambda r: -r[2]):
        print(f"| {engine} | {mean_acc:.2%} | {mean_cer:.2%} | {hits}/{total} | {sec:.1f} |")
    print(f"\nRaw outputs: {RAW_OUT}")


if __name__ == "__main__":
    main()
