"""Deterministic layer: redaction, deadline math, traffic light, calendar export.
The LLM never computes dates, colors or URLs."""
import re
import datetime as dt
from dateutil.relativedelta import relativedelta
import holidays

# ---- Curated office table (TODO: verify every URL and add deep links by hand) ----
OFFICES = {
    "auslaenderbehoerde_nbg": {"name": "Ausländerbehörde Nürnberg", "url": "https://www.nuernberg.de"},
    "jobcenter_nbg": {"name": "Jobcenter Nürnberg-Stadt", "url": "https://www.arbeitsagentur.de"},
    "finanzamt_nbg": {"name": "Finanzamt Nürnberg", "url": "https://www.finanzamt.bayern.de"},
    "familienkasse": {"name": "Familienkasse", "url": "https://www.arbeitsagentur.de"},
    "beratung_nbg": {"name": "Free counselling services in Nuremberg", "url": "https://www.nuernberg.de"},
}

# ---- Step 3: redaction ----
PATTERNS = [
    ("IBAN", r"\b[A-Z]{2}\d{2}(?:\s?\d{4}){4,7}(?:\s?\d{1,4})?\b"),
    ("EMAIL", r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    ("DOB", r"(?i)(?:geb(?:oren|\.)?(?:\s+am)?|geburtsdatum)[:\s]*\d{1,2}\.\d{1,2}\.\d{2,4}"),
    ("REF", r"(?i)\b(?:aktenzeichen|az\.?|kundennummer|bg-nummer|steuernummer|steuer-id|geschäftszeichen|kindergeldnummer|ihr zeichen|unser zeichen)[^\n:]{0,20}[:\s]+[\w./-]+"),
    ("PHONE", r"(?<!\d)(?:\+49|0049|0)[\s/()-]*\d{2,5}[\s/()-]*\d{3,}[\d\s/-]*"),
    ("TAXID", r"(?<!\d)\d{11}(?!\d)"),
    ("ADDR", r"(?m)^.*\b\d{5}\s+[A-ZÄÖÜ][\wäöüß-]+.*$"),
    ("STREET", r"(?m)^.*\b[A-ZÄÖÜ][\wäöüß.-]*(?:straße|str\.|weg|platz|allee|gasse)\s+\d+\w?.*$"),
    ("NAME", r"\b(?:Herrn?|Frau)\s+(?:(?:Dr|Prof)\.\s+)*[A-ZÄÖÜ][\wäöüß-]+(?:\s+[A-ZÄÖÜ][\wäöüß-]+){0,2}"),
]


def redact(text, own_names=()):
    """Return (redacted_text, mapping). Mapping never leaves the device."""
    mapping, counters = {}, {}

    def sub(label):
        def _r(m):
            val = m.group(0)
            for ph, v in mapping.items():
                if v == val:
                    return ph
            counters[label] = counters.get(label, 0) + 1
            ph = f"[{label}_{counters[label]}]"
            mapping[ph] = val
            return ph
        return _r

    for n in [n.strip() for n in own_names if n.strip()]:
        text = re.sub(re.escape(n), sub("NAME"), text, flags=re.I)
    for label, pat in PATTERNS:
        text = re.sub(pat, sub(label), text)
    return text, mapping


def restore(text, mapping):
    for ph, val in mapping.items():
        text = text.replace(ph, val)
    return text


# ---- Step 5: deadline math ----
def _roll(d):
    hol = holidays.Germany(subdiv="BY", years=[d.year, d.year + 1])
    while d.weekday() >= 5 or d in hol:
        d += dt.timedelta(days=1)
    return d


def _parse(s):
    try:
        return dt.date.fromisoformat(s) if s else None
    except ValueError:
        return None


def compute_deadline(d, letter_date, formal_service=False, received=None):
    """Return a date or None (= not computable, ask the user)."""
    if d.get("rule") == "fixed_date":
        return _parse(d.get("fixed_date"))
    n, unit = d.get("amount"), d.get("unit")
    if not n or unit not in ("days", "weeks", "months"):
        return None
    if received:
        base = received
    else:
        if formal_service or not letter_date:
            return None
        base = letter_date
        if d["rule"].endswith("from_bekanntgabe"):
            base += dt.timedelta(days=3)  # presumed Bekanntgabe (§41 VwVfG, §37 SGB X, §122 AO)
    return _roll(base + relativedelta(**{unit: n}))


STRONG = ["widerspruch", "einspruch", "mahnung", "aufhebung", "rückforderung",
          "ablehnung", "anhörung", "meldeversäumnis", "sanktion"]
LABELS = {
    "red": "Act now: a deadline is close, overdue, or the letter is serious.",
    "yellow": "Act soon: there is a deadline, but not immediate.",
    "green": "Information only: no deadline found.",
    "grey": "Could not verify the deadline. Check the original or ask a counselling service.",
}


def traffic_light(res, items, today, low_ocr, redacted_text=""):
    level = 0  # green
    for i in items:
        if i["date"] is None:
            continue
        days = (i["date"] - today).days
        if days <= 14 or (i["kind"] == "appointment" and days <= 7):
            level = 2
        else:
            level = max(level, 1)
    uncertain = (not res.get("deadline_search_complete") or low_ocr
                 or any(i["confidence"] == "low" or i["date"] is None for i in items))
    serious = (res.get("letter_type") in ("bescheid_rejection", "reminder")
               or res.get("escalate_to_human", {}).get("flag")
               or any(k in redacted_text.lower() for k in STRONG))
    if serious:
        level = min(level + 1, 2) if (items or level) else 1
    if uncertain and level < 2:
        return "grey", LABELS["grey"]
    return ["green", "yellow", "red"][level], LABELS[["green", "yellow", "red"][level]]


def build_ics(events):
    """events: list of (summary, date). Reminders 7 and 2 days before."""
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//briefklar//EN"]
    for n, (summary, d) in enumerate(events):
        out += ["BEGIN:VEVENT", f"UID:briefklar-{d:%Y%m%d}-{n}@local",
                f"DTSTAMP:{dt.datetime.utcnow():%Y%m%dT%H%M%SZ}",
                f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"SUMMARY:{summary}"]
        for trig in ("-P7D", "-P2D"):
            out += ["BEGIN:VALARM", f"TRIGGER:{trig}", "ACTION:DISPLAY",
                    f"DESCRIPTION:{summary}", "END:VALARM"]
        out.append("END:VEVENT")
    out.append("END:VCALENDAR")
    return "\r\n".join(out)
