"""Briefklar backend (contract: openapi.yaml): POST /extract (OCR) and POST /analyze (LLM).

    uv run uvicorn api:app --port 8000                              # fast lane (Claude vision)
    BRIEFKLAR_EXTRACTOR=local uv run uvicorn api:app --port 8000    # on-device OCR
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import analysis
from extractors import BadRequest, ExtractionError, UpstreamError, get_extractor, sniff_mime

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 60_000


class ExtractResponse(BaseModel):
    text: str
    pages: int
    warnings: list[str] = []


class AnalyzeRequest(BaseModel):
    text: str
    language: str = Field("en", max_length=20)
    question: str | None = Field(None, max_length=1000)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_extractor().warm_up()  # local OCR: load the model before the first request
    yield


app = FastAPI(title="Briefklar API", version="0.2.0", lifespan=lifespan)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "message": message})


@app.exception_handler(ExtractionError)
async def extraction_error(request: Request, exc: ExtractionError) -> JSONResponse:
    return _error(exc.status, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    if request.url.path == "/analyze":
        return _error(400, "bad_request", "Please send JSON with the letter text: {text, language, question}.")
    return _error(400, "bad_request", "Please upload a file in the 'file' field.")


@app.post("/extract", response_model=ExtractResponse, tags=["ocr"], operation_id="extractText")
def extract_text(file: UploadFile = File(...)) -> ExtractResponse:
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise BadRequest("The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise BadRequest("The file is larger than 20 MB.")
    result = get_extractor().extract(data, sniff_mime(data, file.content_type))
    return ExtractResponse(text=result.text, pages=result.pages, warnings=result.warnings)


@app.post("/analyze", tags=["llm"], operation_id="analyzeLetter")
def analyze_letter(body: AnalyzeRequest) -> dict:
    text = body.text.strip()
    if not text:
        raise BadRequest("The letter text is empty.")
    if len(text) > MAX_TEXT_CHARS:
        raise BadRequest("The letter text is too long.")
    try:
        return analysis.analyze(text, language=body.language, question=body.question)
    except Exception as exc:  # Claude errors and unparsable model output; content is not logged
        raise UpstreamError("Analysis failed, please retry.") from exc


@app.get("/health", include_in_schema=False)
def health() -> dict:
    return {"ok": True}
