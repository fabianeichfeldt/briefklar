import datetime as dt
import hashlib
import streamlit as st
import logic
import llm
from extractors import ExtractionError, LocalOcrExtractor, sniff_mime

LANGS = ["English", "العربية (Arabic)", "Українська (Ukrainian)", "Türkçe (Turkish)", "Русский (Russian)",
         "Română", "فارسی (Persian)", "Español", "Français", "Polski", "Tigrinya", "Kurdî (Kurmanji)"]
COL = {"red": "#B3261E", "yellow": "#C98A00", "green": "#2E7D32", "grey": "#56616D"}  # Briefklar brand traffic light

st.set_page_config(page_title="Briefklar", page_icon="🚦")
st.title("🚦 Briefklar")
st.caption("Understand your German official letter. Personal data is blacked out before anything is sent to the AI. "
           "This is an explanation, not legal advice.")

lang = st.sidebar.selectbox("Your language", LANGS)
own = st.sidebar.text_input("Your name(s), comma-separated (also blacked out)")


@st.cache_resource
def ocr_engine():
    # Always on-device (GLM-OCR): this app promises nothing leaves before redaction.
    extractor = LocalOcrExtractor()
    extractor.warm_up()
    return extractor


def extract(src):
    """Return (text, low_quality). OCR runs once per upload, not on every Streamlit rerun."""
    data = src.getvalue()
    key = hashlib.sha256(data).hexdigest()
    if st.session_state.get("ocr_key") != key:
        try:
            with st.spinner("Reading the letter on your device…"):
                result = ocr_engine().extract(data, sniff_mime(data, getattr(src, "type", None)))
            st.session_state.ocr = (result.text, bool(result.warnings))
        except ExtractionError as e:
            st.session_state.ocr = ("", True)
            st.error(e.message)
        st.session_state.ocr_key = key
    return st.session_state.ocr


# ---- 1 Upload ----
st.subheader("1 · Snap or upload")
cam = st.camera_input("Take a photo", label_visibility="collapsed")
up = st.file_uploader("…or upload a photo / PDF", type=["png", "jpg", "jpeg", "heic", "pdf"])
src = cam or up
if not src:
    st.stop()

# ---- 2 + 3 Read and black out (local) ----
raw, low = extract(src)
if not raw:
    st.stop()
if low:
    st.warning("The text is hard to read. Retake the photo flat, in good light, or the result may be wrong.")
red, mapping = logic.redact(raw, own.split(","))
st.subheader("2 · This is all that leaves your device")
red = st.text_area("Edit if you see personal data that was missed", red, height=260)
ok = st.checkbox("I checked: no personal data is visible")

if st.button("Explain my letter", type="primary", disabled=not ok):
    with st.spinner("Reading…"):
        try:
            st.session_state.res = llm.analyze(red, lang)
            st.session_state.update(red=red, mapping=mapping, low=low, lang=lang)
        except Exception as e:  # noqa: BLE001
            st.error(f"Could not analyse the letter: {e}")

res = st.session_state.get("res")
if not res:
    st.stop()

# ---- 5 Code decides dates and light ----
st.subheader("3 · Your letter, explained")
rec = st.date_input("Date you received the letter (optional, makes deadlines more exact)", value=None)
today = dt.date.today()
ld = logic._parse(res.get("letter_date"))
items = []
for d in res.get("deadlines", []):
    items.append({**d, "date": logic.compute_deadline(d, ld, res.get("formal_service", False), rec)})
color, label = logic.traffic_light(res, items, today, st.session_state.low, st.session_state.red)
fg = "#15202B" if color == "yellow" else "#fff"
st.markdown(f"<div style='background:{COL[color]};color:{fg};padding:14px;border-radius:8px;"
            f"font-weight:600'>{label}</div>", unsafe_allow_html=True)

st.write(res.get("summary", ""))

for i in items:
    if i["date"]:
        st.markdown(f"**{i['kind'].title()}: {i['date']:%d.%m.%Y}** ({(i['date'] - today).days} days)")
    else:
        st.markdown(f"**{i['kind'].title()}: date not computed.** Enter the receipt date above or check the letter.")
    st.caption(f"Letter says: “{i.get('source_quote_de', '')}” · confidence: {i.get('confidence')}")

if res.get("consequence_if_missed"):
    st.error(res["consequence_if_missed"])
if res.get("escalate_to_human", {}).get("flag"):
    st.warning("This case may need personal advice (" + str(res["escalate_to_human"].get("reason")) + "). "
               "Please contact a free counselling service.")
    res.setdefault("office_ids", []).append("beratung_nbg")

if res.get("actions"):
    st.markdown("**Next steps**")
    for a in res["actions"]:
        st.markdown(f"- {a}")

offices = [logic.OFFICES[o] for o in dict.fromkeys(res.get("office_ids", [])) if o in logic.OFFICES]
for o in offices:
    st.markdown(f"🏢 [{o['name']}]({o['url']})")

events = [(f"Deadline: {i['kind']}", i["date"]) for i in items if i["date"]]
if events:
    st.download_button("📅 Add to calendar (.ics)", logic.build_ics(events), "deadline.ics", "text/calendar")

if res.get("reply_needed") and res.get("reply_draft_de"):
    st.markdown("**German reply draft** (your data is filled in here, on your device only)")
    st.text_area("Draft", logic.restore(res["reply_draft_de"], st.session_state.mapping), height=220,
                 label_visibility="collapsed")
    st.caption("What it says, in your language: " + str(res.get("reply_back_translation")))

# ---- Follow-up (also redacted) ----
q = st.text_input("Ask a question about this letter")
if q:
    q_red, _ = logic.redact(q, own.split(","))
    with st.spinner("…"):
        st.write(llm.ask(st.session_state.red, q_red, st.session_state.lang))
