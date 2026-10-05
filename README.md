# Briefklar

**Snap a German official letter. Understand it in your own language, with every deadline and next step.**

Prototype for the **Claude Code Impact Lab, Nürnberg** (5 October 2026) · Track 3: *AI for Good: multilingual access to municipal information*.

> Briefklar explains letters. It is **not legal advice** and **stores no personal data**.

---

## The problem

For many newcomers, the city starts with a letter they can't read.

Letters from the Ausländerbehörde, Jobcenter, Finanzamt or Familienkasse are written in dense legal German, and the deadlines are buried in the fine print. Missing one can cost someone benefits, money or their residence status. People end up relying on friends, Google Translate or long queues at counselling services. The city never finds out which of its letters people misunderstand.

## How it works

| Step | What happens |
|---|---|
| **1. Snap** | Take a photo or upload a PDF of the letter, from any phone. |
| **2. Understand** | Get a plain explanation in one of 40+ languages, with urgency and deadlines. |
| **3. Act** | See next steps, the documents to bring and the right office. Get a calendar entry (`.ics`) and a German reply draft. |

### Example output (fictional MUSTER letter)

> **Your residence permit expires soon. You have an appointment to extend it.**
> From: Stadt Nürnberg, Ausländerbehörde · AB-2026/48213-P · **URGENT**
>
> | Date | What | In |
> |---|---|---|
> | 13.10.2026 | Last day to cancel or move the appointment (**Frist**) | 8 days |
> | 20.10.2026 | Appointment, 09:30, room 2.14 | 15 days |
> | 15.11.2026 | Current permit expires | 41 days |
>
> **What to do**
> - Add the appointment to your calendar.
> - Collect: passport, biometric photo, work contract + 3 payslips, health insurance proof, rental contract.
> - Can't make it? Cancel online before 13.10. A reply draft in German is ready.
>
> **Key terms:** *Aufenthaltstitel* (residence permit) · *Vorsprache* (in-person visit) · *Fortgeltungswirkung* (your permit stays valid while you wait)

## Who benefits

- **Residents:** fewer missed deadlines, less stress, and they pick up bureaucratic German over time.
- **City administration:** fewer calls and repeat visits, plus anonymous data on which letters confuse people.
- **Counselling services:** migration and social counsellors can spend their time on the cases that really need a person.
- **Other cities:** the core stays the same. A new city only needs its own knowledge pack of local service pages.

### City dashboard: anonymous confusion hotspots

The city sees which **topics and letter types** cause confusion, for example residence permit 31%, Jobcenter 23%, Rundfunkbeitrag 16%, tax office 12%, Kita & school 10% (illustrative numbers). The dashboard only counts topic and letter type. It never records names or letter content.

## Stack (hackathon build, ~5 hours)

- **Python + Streamlit** single app
- **Claude API** (vision) for reading the letter and producing structured output
- Grounding in **nuernberg.de** service pages (local knowledge pack)
- `.ics` calendar export and a German reply draft
- City dashboard for confusion hotspots

## Getting started

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
streamlit run app.py
```

## Prepared before the build

- 6 realistic sample letters (fictional, clearly marked **MUSTER**)
- Core Claude prompt with a structured output format
- Guardrails: no invented links, uncertainty is flagged, users are pointed to in-person help


### Local OCR (optional extractor, `BRIEFKLAR_EXTRACTOR=local`)

Document images are read fully offline with **GLM-OCR** (0.9B, bf16) running on Apple Silicon via [MLX](https://github.com/Blaizzy/mlx-vlm). Output is Markdown.

```bash
uv sync                                  # or: pip install -r requirements.txt; installs deps (model downloads on first run, ~2 GB, into ~/.cache/huggingface)
uv run scripts/ocr_documents.py          # OCR samples/*.png → output/ocr/*.md
uv run pytest                            # key fields (dates, IDs, amounts, names) recognised in all sample letters
uv run scripts/eval_ocr.py               # re-run the model bake-off (needs `brew install tesseract-lang` for the baseline)
```

```python
from ocr import ocr_image
print(ocr_image("samples/doc_1.png").text)
```

#### `POST /extract`

```bash
BRIEFKLAR_EXTRACTOR=local uv run uvicorn api:app --port 8000     # default extractor is "claude" (fast lane)
curl -F file=@samples/doc_4.png localhost:8000/extract
# → {"text": "Beitragsservice (Muster)\nRundfunkbeitrag\n…", "pages": 1, "warnings": []}
```

Accepts JPEG, PNG, HEIC and PDF (up to 10 pages, 20 MB), and returns plain text with `pages` and `warnings`. Errors follow `openapi.yaml`: `400 bad_request` for a missing, corrupt or unsupported file, `422 unreadable` when no usable text is found, and `502 upstream_error` if the Claude call fails. Uploads are processed in memory and never logged.

#### Why GLM-OCR — bake-off on the 6 sample letters (M5 Pro)

| Engine | word accuracy | key fields | sec/page |
|---|---|---|---|
| **GLM-OCR bf16, upscaled to 2048 px** (default) | **99.8 %** | **51/51** | 5.3 |
| GLM-OCR 8-bit | 99.1 % | 50/51 | 3.5 |
| dots.ocr 4-bit (3B) | 95.9 % | 51/51 | 5.3 |
| PaddleOCR-VL 1.6 4-bit | 94.5 % | 45/51 | 1.7 |
| Tesseract 5 `deu` | 92.0 % | 43/51 | 0.3 |

Word accuracy is order-independent (share of ground-truth words reproduced exactly). dots.ocr drops letterheads; PaddleOCR-VL misses the reference-number block and writes "Yildiz" for "Yıldız"; Tesseract garbles IDs and `§` references. Ground truth lives in `tests/ground_truth/`, key fields in `tests/key_fields.json`.


## Disclaimer

Briefklar is a prototype. It explains letters but does not give legal advice. All sample letters are fictional. Uploaded letters are processed in-session and never stored.
