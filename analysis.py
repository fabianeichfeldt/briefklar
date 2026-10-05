"""Glue for POST /analyze: llm.py (Claude) + logic.py (dates, light) → openapi.yaml `Analysis`.

Letter text is never logged.
"""

from __future__ import annotations

import datetime as dt

import logic

DISCLAIMER = "Explains, does not advise. Check the deadline against your letter."

# Frontend sends BCP-47 codes; llm.py wants a language name for USER_LANG.
LANGUAGE_NAMES = {
    "en": "English", "de": "German", "uk": "Ukrainian", "ar": "Arabic", "tr": "Turkish",
    "fa": "Persian (Farsi)", "ro": "Romanian", "ru": "Russian", "pl": "Polish", "es": "Spanish",
    "fr": "French", "ti": "Tigrinya", "ku": "Kurdish (Kurmanji)",
}

# llm.py office ids → openapi Office enum
OFFICE_CODES = {
    "auslaenderbehoerde_nbg": "auslaenderbehoerde",
    "jobcenter_nbg": "jobcenter",
    "finanzamt_nbg": "finanzamt",
    "familienkasse": "familienkasse",
}
CITY_OFFICES = {"auslaenderbehoerde_nbg", "jobcenter_nbg"}  # senderVerified (SPEC.md, part B)

LETTER_TYPES = {
    "bescheid_rejection": "decision",
    "bescheid_approval": "decision",
    "invitation": "appointment_invitation",
    "reminder": "reminder",
    "request_documents": "document_request",
    "info_only": "information",
}

DATE_KINDS = {"objection": "frist", "response": "frist", "submission": "frist",
              "appointment": "appointment", "payment": "payment"}
DATE_LABELS = {
    "objection": "Last day to object (Widerspruch / Einspruch)",
    "response": "Last day to reply",
    "submission": "Last day to send documents",
    "appointment": "Appointment",
    "payment": "Payment due",
}


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code.split("-")[0].lower(), code)


def to_analysis(res: dict, redacted_text: str, today: dt.date, answer: str | None = None) -> dict:
    """Map the llm.analyze() JSON to the openapi `Analysis` shape. Dates and light come from logic.py."""
    letter_date = logic._parse(res.get("letter_date"))
    deadlines = res.get("deadlines") or []
    items = [{**d, "date": logic.compute_deadline(d, letter_date, res.get("formal_service", False))}
             for d in deadlines]
    for i in items:
        i.setdefault("confidence", "low")
        i.setdefault("kind", "response")

    color, label = logic.traffic_light(res, items, today, False, redacted_text)
    light = "yellow" if color == "grey" else color  # openapi Light has no grey; unsure → yellow

    uncertainties = []
    dated = []
    for i in items:
        quote = i.get("source_quote_de") or ""
        if i["date"] is None:
            uncertainties.append(f"Date could not be computed exactly. The letter says: „{quote}“")
            continue
        if i.get("confidence") == "low":
            uncertainties.append(f"Please check this date against your letter: „{quote}“")
        dated.append({
            "date": i["date"].isoformat(),
            "daysLeft": (i["date"] - today).days,
            "kind": DATE_KINDS.get(i["kind"], "other"),
            "label": DATE_LABELS.get(i["kind"], i["kind"]),
            "sourceSentence": quote,
        })
    dated.sort(key=lambda d: d["date"])
    upcoming = [d for d in dated if d["kind"] != "appointment"] or dated
    deadline = upcoming[0] if upcoming else None
    other_dates = [d for d in dated if d is not deadline]

    escalate = res.get("escalate_to_human") or {}
    office_ids = list(dict.fromkeys(res.get("office_ids") or []))
    if escalate.get("flag"):
        if escalate.get("reason"):
            uncertainties.append(f"This may need personal advice: {escalate['reason']}")
        office_ids.append("beratung_nbg")
    office_ids = [o for o in dict.fromkeys(office_ids) if o in logic.OFFICES]

    steps = list(res.get("actions") or [])
    if res.get("consequence_if_missed"):
        steps.append(f"⚠️ {res['consequence_if_missed']}")

    primary = next((o for o in office_ids if o in OFFICE_CODES), None)
    return {
        "today": today.isoformat(),
        "light": light,
        "lightReason": label,
        "deadline": deadline,
        "otherDates": other_dates,
        "meaning": res.get("summary") or "",
        "answer": answer,
        "steps": steps,
        "documents": res.get("documents") or [],
        "sources": [{"title": logic.OFFICES[o]["name"], "url": logic.OFFICES[o]["url"]} for o in office_ids],
        "glossary": res.get("glossary") or [],
        "draftDe": res.get("reply_draft_de") or "",
        "office": OFFICE_CODES.get(primary, "other"),
        "letterType": LETTER_TYPES.get(res.get("letter_type"), "other"),
        "senderVerified": any(o in CITY_OFFICES for o in office_ids),
        "uncertainties": uncertainties,
        "disclaimer": DISCLAIMER,
    }


def analyze(text: str, language: str = "en", question: str | None = None,
            today: dt.date | None = None) -> dict:
    import llm  # creates the Anthropic client on import

    lang = language_name(language)
    res = llm.analyze(text, lang)
    answer = llm.ask(text, question, lang) if question else None
    return to_analysis(res, text, today or dt.date.today(), answer)
