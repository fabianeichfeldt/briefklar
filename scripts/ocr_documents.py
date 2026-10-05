"""Run OCR over every image in samples/ and write Markdown to output/ocr/.

    uv run scripts/ocr_documents.py [--model mlx-community/GLM-OCR-bf16]
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # ocr.py lives in the repo root

from ocr import DEFAULT_MODEL, ocr_image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--input", type=Path, default=ROOT / "samples")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "ocr")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    images = sorted(p for p in args.input.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"})
    total = 0.0
    for image in images:
        result = ocr_image(image, model_id=args.model)
        (args.output / f"{image.stem}.md").write_text(result.text + "\n", encoding="utf-8")
        total += result.seconds
        print(f"{image.name}: {result.seconds:.1f}s, {len(result.text)} chars")
    print(f"{len(images)} images in {total:.1f}s with {args.model} → {args.output}")


if __name__ == "__main__":
    main()
