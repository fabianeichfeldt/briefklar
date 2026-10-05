import json
import os
import anthropic
from logic import OFFICES

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
FAST_MODEL = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5-20251001")  # quick overview
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY

SCHEMA = """{
 "letter_type": "bescheid_rejection|bescheid_approval|invitation|reminder|request_documents|info_only|other",
 "summary": "plain explanation in USER_LANG; keep key German terms in brackets, e.g. Widerspruch (objection)",
 "letter_date": "YYYY-MM-DD or null",
 "formal_service": false,
 "deadline_search_complete": true,
 "deadlines": [{"kind": "objection|response|appointment|payment|submission",
   "rule": "fixed_date|days_from_letter|days_from_bekanntgabe|months_from_bekanntgabe",
   "fixed_date": "YYYY-MM-DD or null", "amount": 1, "unit": "days|weeks|months|null",
   "source_quote_de": "exact German sentence from the letter", "confidence": "high|medium|low"}],
 "actions": ["short step in USER_LANG"],
 "consequence_if_missed": "USER_LANG or null",
 "office_ids": ["ids from the allowed list only"],
 "reply_needed": false,
 "reply_draft_de": "German reply, keep [PLACEHOLDERS] untouched, or null",
 "reply_back_translation": "the draft translated to USER_LANG, or null",
 "escalate_to_human": {"flag": false, "reason": null}
}"""


# Quick first look: what is it, how urgent, do I have to act. Same deadline format as SCHEMA,
# so logic.py computes the dates and the traffic light exactly like for the full analysis.
OVERVIEW_SCHEMA = """{
 "letter_type": "bescheid_rejection|bescheid_approval|invitation|reminder|request_documents|info_only|other",
 "summary": "ONE short sentence in USER_LANG: who wrote and what they want",
 "action_needed": true,
 "next_step": "the single most important thing to do, one short sentence in USER_LANG, or null",
 "letter_date": "YYYY-MM-DD or null",
 "formal_service": false,
 "deadline_search_complete": true,
 "deadlines": [{"kind": "objection|response|appointment|payment|submission",
   "rule": "fixed_date|days_from_letter|days_from_bekanntgabe|months_from_bekanntgabe",
   "fixed_date": "YYYY-MM-DD or null", "amount": 1, "unit": "days|weeks|months|null",
   "source_quote_de": "exact German sentence from the letter", "confidence": "high|medium|low"}],
 "office_ids": ["ids from the allowed list only"],
 "escalate_to_human": {"flag": false, "reason": null}
}"""


def _system(lang, schema=SCHEMA):
    offices = "\n".join(f"- {k}: {v['name']}" for k, v in OFFICES.items())
    return (
        "You explain German official letters to people who do not read German well. "
        "You give orientation, not legal advice. Placeholders like [NAME_1] stand for redacted personal data: keep them as they are. "
        "NEVER compute final dates, choose colors, or write URLs. For each deadline return the rule as written in the letter "
        "plus the exact German source sentence. If you are unsure about a deadline, say confidence low. "
        "Set deadline_search_complete=false if the text looks cut off or unreadable. "
        "Flag escalate_to_human for objections, residence-status decisions, benefit cuts or repayments.\n"
        f"USER_LANG = {lang}\nAllowed office ids:\n{offices}\n"
        f"Return ONLY JSON, no markdown, matching:\n{schema}"
    )


def _text(r):
    # Sonnet 5.5 thinks by default, so content[0] can be a thinking block.
    return "".join(b.text for b in r.content if b.type == "text")


def _json(text):
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


def analyze(redacted_text, lang):
    r = client.messages.create(
        model=MODEL, max_tokens=3000, system=_system(lang),
        messages=[{"role": "user", "content": f"Letter (redacted):\n\n{redacted_text}"}],
    )
    return _json(_text(r))


def overview(redacted_text, lang):
    r = client.messages.create(
        model=FAST_MODEL, max_tokens=1000, system=_system(lang, OVERVIEW_SCHEMA),
        messages=[{"role": "user", "content": f"Letter (redacted):\n\n{redacted_text}"}],
    )
    return _json(_text(r))


def ask(redacted_text, redacted_question, lang):
    r = client.messages.create(
        model=MODEL, max_tokens=800,
        system=(f"Answer in {lang}, briefly, based only on the redacted German letter. "
                "Orientation, not legal advice. Do not state dates you cannot read in the letter. "
                "Placeholders like [NAME_1] stay as they are."),
        messages=[{"role": "user", "content": f"Letter:\n{redacted_text}\n\nQuestion: {redacted_question}"}],
    )
    return _text(r)
