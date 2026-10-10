"""POST /analyze glue: llm.py output → openapi `Analysis` (no Claude calls)."""

import datetime as dt
import sys
import types

from fastapi.testclient import TestClient

import analysis
import api

client = TestClient(api.app)
TODAY = dt.date(2026, 10, 5)

LLM_RESULT = {
    "letter_type": "invitation",
    "summary": "Your residence permit expires soon. You have an appointment to extend it.",
    "letter_date": "2026-09-24",
    "formal_service": False,
    "deadline_search_complete": True,
    "deadlines": [
        {"kind": "appointment", "rule": "fixed_date", "fixed_date": "2026-10-20", "amount": None, "unit": None,
         "source_quote_de": "Termin: Dienstag, 20.10.2026, 09:30 Uhr", "confidence": "high"},
        {"kind": "response", "rule": "fixed_date", "fixed_date": "2026-10-13", "amount": None, "unit": None,
         "source_quote_de": "sagen Sie ihn bitte spätestens bis zum 13.10.2026 ab", "confidence": "high"},
        {"kind": "objection", "rule": "months_from_bekanntgabe", "fixed_date": None, "amount": 1, "unit": "months",
         "source_quote_de": "innerhalb eines Monats nach Bekanntgabe", "confidence": "medium"},
    ],
    "actions": ["Go to the appointment on 20.10.2026."],
    "documents": ["Passport (Reisepass)", "Biometric photo (biometrisches Lichtbild)"],
    "glossary": [{"term": "Fortgeltungswirkung", "explanation": "your permit stays valid while you wait"},
                 {"term": "Vorsprache"}, "Aufenthaltstitel"],
    "consequence_if_missed": None,
    "office_ids": ["auslaenderbehoerde_nbg", "made_up_office"],
    "reply_needed": True,
    "reply_draft_de": "Sehr geehrte Damen und Herren, ... [NAME_1]",
    "reply_back_translation": "Dear Sir or Madam, ...",
    "escalate_to_human": {"flag": False, "reason": None},
}

REQUIRED = {"today", "light", "lightReason", "meaning", "steps", "documents", "sources", "draftDe",
            "office", "letterType", "senderVerified", "uncertainties", "disclaimer"}


def test_maps_llm_output_to_analysis():
    a = analysis.to_analysis(LLM_RESULT, "Termin ...", TODAY)
    assert REQUIRED <= a.keys()
    assert a["light"] == "red"  # 13.10. is 8 days away
    assert a["deadline"]["date"] == "2026-10-13"
    assert a["deadline"]["daysLeft"] == 8
    assert a["deadline"]["kind"] == "frist"
    assert [d["date"] for d in a["otherDates"]] == ["2026-10-20", "2026-10-27"]
    assert a["office"] == "auslaenderbehoerde"
    assert a["letterType"] == "appointment_invitation"
    assert a["senderVerified"] is True
    assert [s["title"] for s in a["sources"]] == ["Ausländerbehörde Nürnberg"]  # unknown office ids dropped
    assert a["draftDe"].endswith("[NAME_1]")
    assert a["documents"] == ["Passport (Reisepass)", "Biometric photo (biometrisches Lichtbild)"]
    assert a["glossary"] == [{"term": "Fortgeltungswirkung",
                              "explanation": "your permit stays valid while you wait"}]  # malformed items dropped


def test_grey_becomes_yellow_and_undated_deadline_is_flagged():
    res = {**LLM_RESULT, "letter_date": None, "deadlines": [LLM_RESULT["deadlines"][2]], "office_ids": []}
    a = analysis.to_analysis(res, "", TODAY)
    assert a["light"] == "yellow"
    assert a["deadline"] is None
    assert any("could not be computed" in u for u in a["uncertainties"])
    assert a["senderVerified"] is False and a["office"] == "other"


def test_endpoint_passes_language_name_and_question(monkeypatch):
    calls = {}
    fake = types.ModuleType("llm")
    fake.analyze = lambda text, lang: calls.setdefault("analyze", lang) and LLM_RESULT
    fake.ask = lambda text, q, lang: f"answer to {q}"
    monkeypatch.setitem(sys.modules, "llm", fake)
    r = client.post("/analyze", json={"text": "Brieftext", "language": "uk", "question": "Muss ich hin?"})
    assert r.status_code == 200
    assert calls["analyze"] == "Ukrainian"
    assert r.json()["answer"] == "answer to Muss ich hin?"


def test_endpoint_errors(monkeypatch):
    assert client.post("/analyze", json={"text": "  "}).json()["code"] == "bad_request"
    assert client.post("/analyze", json={}).status_code == 400

    fake = types.ModuleType("llm")
    fake.analyze = lambda text, lang: (_ for _ in ()).throw(ValueError("no json"))
    monkeypatch.setitem(sys.modules, "llm", fake)
    r = client.post("/analyze", json={"text": "Brieftext"})
    assert r.status_code == 502 and r.json()["code"] == "upstream_error"


OVERVIEW_RESULT = {k: LLM_RESULT[k] for k in
                   ("letter_type", "letter_date", "formal_service", "deadline_search_complete",
                    "deadlines", "office_ids", "escalate_to_human")}
OVERVIEW_RESULT |= {"summary": "The Ausländerbehörde invites you to extend your permit.",
                    "action_needed": True, "next_step": "Go to the appointment on 20.10.2026."}


def test_overview_has_same_light_and_deadline_as_full_analysis():
    o = analysis.to_overview(OVERVIEW_RESULT, "Termin ...", TODAY)
    a = analysis.to_analysis(LLM_RESULT, "Termin ...", TODAY)
    assert REQUIRED <= o.keys()
    assert o["depth"] == "overview" and a["depth"] == "full"
    assert (o["light"], o["deadline"]) == (a["light"], a["deadline"])
    assert o["actionNeeded"] is True
    assert o["steps"] == ["Go to the appointment on 20.10.2026."]
    assert o["draftDe"] == "" and o["documents"] == [] and o["glossary"] == []


def test_overview_endpoint(monkeypatch):
    fake = types.ModuleType("llm")
    fake.overview = lambda text, lang: {**OVERVIEW_RESULT, "action_needed": False, "next_step": None}
    monkeypatch.setitem(sys.modules, "llm", fake)
    r = client.post("/overview", json={"text": "Brieftext", "language": "tr"})
    assert r.status_code == 200
    assert r.json()["actionNeeded"] is False and r.json()["steps"] == []
    assert client.post("/overview", json={"text": " "}).json()["code"] == "bad_request"
