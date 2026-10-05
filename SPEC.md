# Briefklar: Build Spec (hackathon, 5 Oct 2026)

A minimal spec that splits the build into three parts so people can work in parallel. Source: the build plan artifact (`Briefklar Build Plan.html`).

**Goal for today:** you photograph an official letter. Your personal data is blacked out on your device. You get a traffic light, a plain explanation, next steps with official Nuremberg links and a German reply draft. The city gets grouped, non-personal insights about which letters cause questions.

## Flow and ownership

```
 [1 Upload] → [2 OCR] → [3 Redact] → [4 Claude] → [5 Traffic light] → [6 Citizen screen]
   FRONTEND    OCR        OCR         LLM          LLM (plain code)      FRONTEND
                                                                          │ counts only
                                                    [8 City screen] ← [7 Count question type]
                                                      FRONTEND          FRONTEND
```

| Part | Owns | Owner |
|---|---|---|
| **A. OCR & redaction** | Steps 2–3: text recognition and blacking out, both on the device | _tbd_ |
| **B. LLM** | Steps 4–5: understand, explain, draft, deadline, traffic light | _tbd_ |
| **C. Frontend** | Steps 1, 6–8: upload, citizen screen, follow-up chat, city screen | _tbd_ |

**Privacy rule (target state):** Claude only ever sees redacted text. Raw photos and the placeholder mapping never leave the device.

> **Fast lane (now):** to get a working pipeline right away, step 2 starts as a Claude vision call that extracts the text, and local OCR is swapped in later. While the fast lane is active, the raw image goes to Claude and the privacy rule above does **not** hold yet. Only use MUSTER letters, and never pitch the privacy promise on the fast-lane path.

---

## Interfaces (agree on these in the first 10 minutes)

The HTTP contract is in **[`openapi.yaml`](openapi.yaml)** and takes precedence over the sketches below. **v0.2 starts with only `POST /extract` and `POST /analyze`**; redaction, follow-ups and city endpoints come later. The frontend can start against a mock right away: `npx @stoplight/prism-cli mock openapi.yaml`.

These contracts are what keep the three parts independent. Until the upstream part is ready, build against the hand-redacted sample letter (`samples/muster_auslaenderbehoerde.redacted.txt`).

### Upload → A: `TextExtractor` (swappable)

```python
class TextExtractor(Protocol):
    def extract(self, file: bytes, mime: str) -> str: ...   # raw letter text, German

class ClaudeVisionExtractor:  # fast lane, available now
    ...
class LocalOcrExtractor:      # GLM-OCR on MLX (ocr.py), implemented
    ...

EXTRACTOR = os.getenv("BRIEFKLAR_EXTRACTOR", "claude")  # backend setting: "claude" | "local", never set by the client
```

The rest of the pipeline only ever sees the returned string. It must not know which extractor produced it.

### A → B: `RedactedLetter`

```python
@dataclass
class RedactedLetter:
    text: str                  # full OCR text, personal data replaced by placeholders
    placeholders: list[str]    # e.g. ["[NAME]", "[ADDRESS]", "[BIRTHDATE]", "[FILE_NO]", "[IBAN]"]
    # The mapping placeholder → original value stays local and is never passed to B.
```

### B → C: `Analysis`

```python
@dataclass
class Analysis:
    meaning: str               # plain explanation in the user's language (English today)
    steps: list[str]
    documents: list[str]
    deadline_date: date | None
    source_sentence: str | None  # exact sentence in the letter the deadline came from
    source_links: list[str]      # only from the saved Nuremberg pages, never invented
    draft_de: str                # German reply draft, still containing the placeholders
    office: str                  # e.g. "Ausländerbehörde"
    letter_type: str
    question_type: str
    sender_verified: bool        # True only for city offices covered by our sources
    light: Literal["red", "yellow", "green"]  # set by our code, not by Claude
```

### C → city: `QuestionEvent`

```python
{"office": str, "letter_type": str, "question_type": str, "ts": datetime}
# No letter text and no personal words.
```

---

## A. OCR & redaction (on the device)

Built in two stages behind the `TextExtractor` interface:

1. **Fast lane (start now):** `ClaudeVisionExtractor` sends the image or PDF to Claude with a strict "transcribe verbatim, don't interpret" prompt and returns plain text. This is a separate call from the analysis in part B, so the extracted text still goes through redaction before analysis.
2. **Local OCR (implemented):** `LocalOcrExtractor` uses GLM-OCR (0.9B) on Apple Silicon via MLX; it beat Tesseract `deu`, PaddleOCR-VL and dots.ocr on the six MUSTER letters (README). Switching to it is a single config change (`BRIEFKLAR_EXTRACTOR=local`) and needs no code changes elsewhere.

Redaction:
- Redaction uses simple rules: the address block top left, the greeting and signature, birth dates, file numbers and IBANs. Deadlines and amounts are kept.
- The module returns a `RedactedLetter`, and C shows a preview of exactly the text that will be sent.

**Done when (fast lane):** all six MUSTER letters are transcribed by Claude and redacted, with no name, address or file number left in the text passed to part B.
**Done when (local OCR):** the same six letters come out of local OCR just as readable, and `BRIEFKLAR_EXTRACTOR=local` is the default.

## B. LLM: understand, explain, urgency

- About ten official Nuremberg pages are saved as text in `knowledge/` and put into the prompt (grounding happens in the answer step, not after it).
- One Claude call always returns the agreed format (tool use / JSON schema).
- There is no separate translation step. Claude writes `meaning` and `steps` directly in the user's language, and `draft_de` stays German.
- Follow-up questions continue the same thread for that letter.
- Senders that aren't city offices (e.g. Finanzamt, Familienkasse) get `sender_verified = False`, and the answer is marked "uncertain".
- **Traffic light is plain code, not Claude.** Claude only returns the date:
  - overdue, or 14 days or less from today → **red**
  - later than 14 days → **yellow**
  - no deadline (info only) → **green**
  - unsure (no date found, or sender not verified) → **yellow**

**Done when:** the Ausländerbehörde letter returns the right deadline, at least one city link and a draft with placeholders.

## C. Frontend (Streamlit)

**Citizen screen**
- Upload (photo/PDF, with an optional question), followed by the redaction preview.
- The traffic light with the date and the source sentence it came from.
- The explanation, next steps, documents, links and the German draft.
- One chat thread per letter for follow-up questions.
- A visible line on every result: *"Explains, does not advise. Check the deadline against your letter."*

**City screen**
- 30–50 simulated entries with a clear "simulated data" label.
- Counts per office and question type, and the passage that caused the most questions.
- One suggestion for a clearer version of that passage.
- Live moment: a question asked in the citizen screen raises a counter here.

**Done when:** someone outside the team gets from photo to explanation without help, and the city view answers "which letter confuses people, and where" at a glance.

---

## Timeline

| Time | Checkpoint |
|---|---|
| first 10 min | Agree on field names, hand-redact one sample, ask the city rep whether they'd act on this data |
| 15:00 | One letter runs end to end, even if it looks rough |
| 16:30 | Feature stop. Anything unfinished moves to "next steps" |
| 17:00 | Build the submission artifact, rehearse the pitch |
| 18:00 | Submit as a public artifact with the event code (pitches at 18:30) |

## Not today

- Calendar entries (`.ics`)
- Languages other than English
- Warnings when a required document takes weeks to get
- Non-city sources such as the broadcasting fee office (only if time is left after 16:30)
