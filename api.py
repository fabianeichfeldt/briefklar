"""Briefklar backend (contract: openapi.yaml).

    uv run uvicorn api:app --port 8000                              # fast lane (Claude vision)
    BRIEFKLAR_EXTRACTOR=local uv run uvicorn api:app --port 8000    # on-device OCR
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from extractors import BadRequest, ExtractionError, get_extractor, sniff_mime

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class ExtractResponse(BaseModel):
    text: str
    pages: int
    warnings: list[str] = []


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
