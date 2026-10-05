# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

**Briefklar** turns a photo or PDF of a German official letter (Ausländerbehörde, Jobcenter, Finanzamt, Familienkasse, Rundfunkbeitrag, Kita/school…) into a plain-language explanation in the user's own language. The explanation covers urgency, every deadline, next steps, the documents to bring, the right office, an `.ics` calendar entry and a German reply draft.

It is a 5-hour hackathon prototype for the Claude Code Impact Lab Nürnberg (5 Oct 2026, Track 3: AI for Good). Optimise for **one strong, reliable demo**, not for production breadth.

The original concept artifact is `Briefklar Concept Sheet.html` (the content lives in `Briefklar Concept Sheet_files/saved_resource.html`). Treat it as the source of truth for scope and the example output.

## Stack

- Python 3.11+, **Streamlit** (single app, no separate backend)
- **Anthropic Python SDK** with a vision-capable model. Default `claude-sonnet-5-5`, and use `claude-opus-5-5` for hard or low-quality scans. Keep the model ID in one config constant.
- `ANTHROPIC_API_KEY` from the environment. Never hard-code or commit keys.
- Keep dependencies minimal: `streamlit`, `anthropic`, `ics` (or a hand-written VCALENDAR), plus `pypdf`/`pdf2image` only if PDF support needs them.

## Intended layout (create as needed)

```
app.py                 # Streamlit entry: upload → result → downloads; tab for city dashboard
briefklar/
  prompt.py            # system prompt + output schema
  decode.py            # Claude call, parses/validates structured output
  ics.py               # deadlines/appointments → .ics
  knowledge/           # nuernberg.de service-page snippets (the "knowledge pack")
  stats.py             # anonymous topic/letter-type counters for the dashboard
samples/               # fictional MUSTER letters (images/PDFs)
```

## Core contract: structured output

The Claude call must return structured JSON (use tool use or a JSON schema, not free text). It should contain at least:

- `summary`: one-sentence plain explanation in the target language
- `sender`: authority, department, reference number (Aktenzeichen)
- `urgency`: `urgent` | `soon` | `info`
- `deadlines[]`: `date` (ISO), `label`, `type` (Frist / appointment / expiry), `is_legal_deadline`
- `actions[]`: concrete next steps; `documents[]` to bring
- `office`: name, address, contact. Only fill this if it is present in the letter or the knowledge pack.
- `glossary[]`: German term → explanation (e.g. *Fortgeltungswirkung*)
- `reply_draft_de`: short, polite German reply (e.g. reschedule/cancel)
- `topic` + `letter_type`: coarse categories, the **only** data that goes to the dashboard
- `uncertainties[]`: anything unreadable, ambiguous or inferred

Compute the "days left" counts in Python from the current date, not in the model.

## Guardrails (non-negotiable)

- **No invented links, phone numbers, addresses or legal facts.** Use only what the letter or the knowledge pack contains. If the information is missing, say so.
- **Flag uncertainty** explicitly. When a deadline or the stakes are unclear, point the user to in-person help (Ausländerbehörde, Migrationsberatung, Jobcenter counter).
- Show the **"not legal advice"** notice on every result.
- **No personal data stored.** Process uploads in memory only. Do not log letter content or names. Dashboard stats record only `topic` and `letter_type`.
- Keep German legal terms visible next to the translation so users learn them over time.
- All sample letters are fictional and marked **MUSTER**. Never add real letters to the repo.

## Languages

Support any target language Claude handles (the pitch says 40+). The demo should show at least English, Ukrainian, Arabic (RTL), Turkish, Farsi (RTL) and Romanian. Make sure RTL text renders correctly in Streamlit.

## Commands

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Working style for this repo

- Hackathon pace: small, working increments. Keep the demo path (upload sample → decoded result → `.ics` + reply draft) working after every change.
- Check prompt or schema changes against all 6 MUSTER samples before calling them done.
- Keep everything that is city-specific (knowledge pack, office data) in `knowledge/`, so another city can swap it out without touching the core.
