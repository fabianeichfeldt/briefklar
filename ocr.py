"""Local OCR for document images, backed by document-specialised VLMs on MLX.

Usage:
    from ocr import ocr_image
    result = ocr_image("samples/doc_1.png")
    print(result.text)
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image

# Chosen by scripts/eval_ocr.py: best word accuracy and key-field recall on samples/.
DEFAULT_MODEL = "mlx-community/GLM-OCR-bf16"

# Each OCR model is trained on its own task prompt; using anything else degrades output.
MODEL_PROMPTS = {
    "GLM-OCR": "Text Recognition:",
    "PaddleOCR-VL": "OCR:",
    "dots.ocr": "Extract the text content from this image.",
}

# Upscaling the ~110 dpi sample letters to 2048 px cut GLM-OCR word errors from 1.2 % to 0.2 %.
MIN_LONG_SIDE = 2048


@dataclass
class OcrResult:
    text: str
    model_id: str
    seconds: float
    truncated: bool = False  # hit max_tokens, so the end of the page may be missing


def prompt_for(model_id: str) -> str:
    for family, prompt in MODEL_PROMPTS.items():
        if family.lower() in model_id.lower():
            return prompt
    raise ValueError(f"No OCR prompt registered for {model_id!r}")


@lru_cache(maxsize=1)
def _load(model_id: str):
    from mlx_vlm import load

    return load(model_id)


# MLX GPU streams are thread-local: a model loaded on one thread fails on another
# ("There is no Stream(gpu, 1) in current thread"). FastAPI serves requests from a
# thread pool, so every MLX call runs on this single worker thread (which also
# serialises generation).
_mlx_thread = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mlx")


def preload(model_id: str = DEFAULT_MODEL) -> None:
    """Load the model ahead of the first request (download on first run)."""
    _mlx_thread.submit(_load, model_id).result()


def upscale_if_small(image: Image.Image) -> Image.Image:
    long_side = max(image.size)
    if long_side >= MIN_LONG_SIDE:
        return image
    scale = MIN_LONG_SIDE / long_side
    return image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )


def ocr_pil(
    image: Image.Image,
    model_id: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    upscale: bool = True,
) -> OcrResult:
    """OCR an in-memory image; nothing is written to disk."""
    from mlx_vlm import generate
    from mlx_vlm.prompt_utils import apply_chat_template

    image = image.convert("RGB")
    if upscale:
        image = upscale_if_small(image)

    def run():
        model, processor = _load(model_id)
        prompt = apply_chat_template(processor, model.config, prompt_for(model_id), num_images=1)
        return generate(
            model,
            processor,
            prompt,
            image=[image],
            max_tokens=max_tokens,
            temperature=0.0,
            verbose=False,
        )

    start = time.perf_counter()
    result = _mlx_thread.submit(run).result()
    return OcrResult(
        text=result.text.strip(),
        model_id=model_id,
        seconds=time.perf_counter() - start,
        truncated=result.generation_tokens >= max_tokens,
    )


def ocr_image(path: str | Path, model_id: str = DEFAULT_MODEL, **kwargs) -> OcrResult:
    return ocr_pil(Image.open(path), model_id=model_id, **kwargs)
