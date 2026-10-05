import datetime as dt
import io
import streamlit as st
import pytesseract
from PIL import Image
from pypdf import PdfReader
import logic
import llm

LANGS = ["English", "العربية (Arabic)", "Українська (Ukrainian)", "Türkçe (Turkish)", "Русский (Russian)",
         "Română", "فارسی (Persian)", "Español", "Français", "Polski", "Tigrinya", "Kurdî (Kurmanji)"]
COL = {"red": "#e5484d", "yellow": "#f5b301", "green": "#30a46c", "grey": "#8b8d98"}

st.set_page_config(page_title="Briefklar", page_icon="🚦")
st.title("🚦 Briefklar")
st.caption("Understand your German official letter. Personal data is blacked out before anything is sent to the AI. "
           "This is an explanation, not legal advice.")

lang = st.sidebar.selectbox("Your language", LANGS)
own = st.sidebar.text_input("Your name(s), comma-separated (also blacked out)")


def extract(src):
    data = src.getvalue()
    if src.name.lower().endswith(".pdf") if hasattr(src, "name") and src.name else False:
        text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
        return text, len(text.strip()) < 100
    img = Image.open(io.BytesIO(data))
    d = pytesseract.image_to_data(img, lang="deu", output_type=pytesseract.Output.DICT)
    confs = [float(c) for w, c in zip(d["text"], d["conf"]) if w.strip() and float(c) >= 0]
    low = not confs or sum(confs) / len(confs) < 60
    return pytesseract.image_to_string(img, lang="deu"), low


# ---- 1 Upload ----
st.subheader("1 · Snap or upload")
cam = st.camera_input("Take a photo", label_visibility="collapsed")
up = st.file_uploader("…or upload a photo / PDF", type=["png", "jpg", "jpeg", "pdf"])
src = cam or up
if not src:
    st.stop()

# ---- 2 + 3 Read and black out (local) ----
raw, low = extract(src)
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
fg = "#111" if color in ("yellow", "grey") else "#fff"
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
