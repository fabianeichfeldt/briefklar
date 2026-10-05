# Mobile frontend v1: design

Date: 2026-10-05 · Part C (Frontend) of [`SPEC.md`](../../../SPEC.md) · Contract: [`openapi.yaml`](../../../openapi.yaml)

## Decisions

- **Mobile first.** The phone is the number 1 entry point. Desktop just shows the same column centred (max-width ~480px).
- **Chat-first UI.** One conversation per letter, WhatsApp-like. A red/yellow/green **deadline banner sticks under the header** once a deadline is known, so urgency never scrolls away.
- **Vue 3 + Vite** in `frontend/`, `<script setup>`, plain CSS, no UI library, no Pinia, no router. This deviates from the Streamlit default in `CLAUDE.md` because Streamlit can't do a native rear-camera capture, a controllable chat UI or on-device redaction.
- **Redaction runs in the browser.** Only redacted text goes to `/analyze`. The placeholder → original mapping never leaves the device.
- Caveat: while the backend uses the Claude-vision fast lane, `/extract` still receives the raw photo. Use MUSTER letters only and don't pitch "nothing leaves your phone" yet.

## Flow

1. **Start.** Bot greeting + privacy promise. Three big actions: `📸 Take a photo` (primary), `🖼️ Upload photo / PDF`, `🧪 Try a MUSTER letter`. Optional question in the composer. Language picker in the header.
2. **Capture.** `<input type="file" accept="image/*" capture="environment">` for the camera, `accept="image/*,application/pdf"` for upload. Images are downscaled in the browser (longest side ≤ 2000px, JPEG q≈0.85). PDFs pass through unchanged. The user sees their photo as a thumbnail bubble.
3. **Extract.** `POST /extract` (multipart `file`). The MUSTER button skips this and uses the bundled sample text.
4. **Privacy check.** `redact()` runs locally. The bot shows a "paper" bubble with the redacted text and placeholder tags (`[NAME]`, `[ADDRESS]`, `[FILE_NO]`…). Tapping a placeholder reveals it (un-hides); tapping any other word hides it as `[HIDDEN]`. Buttons: `✨ Looks good, explain it`.
5. **Analyze.** `POST /analyze` with `{ text: redactedText, language, question }`. The answer arrives as several short bot bubbles:
   - urgency pill + office (+ ✓ if `senderVerified`) + `meaning`; `answer` if a question was asked
   - ✅ steps as a checklist + the deadline's `sourceSentence` quoted
   - 🎒 documents
   - uncertainties (if any) with a hint to get in-person help
   - disclaimer (`disclaimer` from the response, always shown)
   - quick-reply chips: `✉️ Reply in German`, `📖 German words`, `🔗 Official pages`. Each chip appends a bubble (draft with copy button, glossary list, sources list).
6. **Follow-ups.** After the result the composer says "Ask about your letter…". Sending calls `/analyze` again with the same redacted text and the new question and shows `answer` as a bot bubble (banner updates from the new response).
7. **New letter.** A 📸 button in the composer / header starts a fresh conversation.

German reply draft: placeholders in `draftDe` are filled back in from the local mapping before display, so it's ready to copy. This happens only in the browser.

## Deadline banner

Shown when `analysis` exists. Colour from `light`. Text: `⏰ {daysLeft} days left · {deadline.label} · {date}`. Overdue (`daysLeft < 0`): "Overdue by N days". No deadline: green "No deadline found" (or yellow with `lightReason` if light is yellow). `daysLeft` comes from the server; the frontend never asks the model to count.

## Languages / RTL

Picker offers en, uk, ar, tr, fa, ro (sent as `language`; the backend may only honour `en` today). For `ar`/`fa`, explanation bubbles get `dir="rtl"`. German text (paper bubble, draft, quoted source sentence, glossary terms) always stays `dir="ltr"` via `<bdi>`/`dir` attributes. CSS uses logical properties (`margin-inline-start` etc.).

UI chrome strings are English in v1.

## Errors

- `422 unreadable` → bot bubble with the server `message` + `📸 Retake` chip.
- `400` → show the server `message`.
- `502` / network / timeout → "Something went wrong" + `↻ Try again` chip that repeats the last request.
- A typing indicator bubble is shown while any request is in flight.

## Code layout

```
frontend/
  package.json, vite.config.js, index.html
  src/
    main.js, App.vue, styles.css
    lib/api.js          # extractText(file), analyzeLetter({text, language, question})
    lib/image.js        # downscaleImage(file) → Blob/File
    lib/redact.js       # redact(text) → {text, placeholders, mapping}; fillPlaceholders(text, mapping)
    lib/sample.js       # SAMPLE_LETTER_TEXT (fictional MUSTER Ausländerbehörde letter)
    composables/useConversation.js
    components/AppHeader.vue, DeadlineBanner.vue, ChatThread.vue, Composer.vue,
               bubbles/RedactionPreview.vue, AnalysisAnswer.vue, DraftDe.vue, Glossary.vue, Sources.vue
  tests/redact.test.js  # vitest
```

`VITE_API_BASE` sets the backend URL, default `http://127.0.0.1:4010` (Prism mock: `npx @stoplight/prism-cli mock openapi.yaml`). `npm run dev -- --host` to open it on a phone in the same Wi-Fi.

## Interfaces

### `lib/redact.js`

```js
redact(text) → {
  text: string,                 // with placeholders like [NAME], [ADDRESS], [FILE_NO], [BIRTHDATE], [IBAN], [EMAIL], [PHONE]
  placeholders: string[],       // distinct placeholders used, in order of first appearance
  mapping: Record<string,string>// placeholder → original; repeated values reuse the same placeholder; distinct values of one kind are numbered: [NAME], [NAME_2]
}
fillPlaceholders(text, mapping) → string
```

Rules (German letters): names after `Herr`/`Frau` (incl. in the salutation `Sehr geehrte/r …`), the recipient address block (a line with a street + house number, and a line with a 5-digit postcode + city, when it is not the authority's own address line), values after `Aktenzeichen`, `Az.`, `Kundennummer`, `BG-Nummer`, `Steuer-ID`, `Ihr Zeichen`; dates preceded by `geb.`/`geboren am`; IBANs; emails; phone numbers. Dates that are deadlines/appointments, money amounts and the authority name are kept. Being too strict is better than leaking.

### `lib/api.js`

```js
extractText(file: Blob) → Promise<{text, pages, warnings}>
analyzeLetter({text, language, question}) → Promise<Analysis>   // Analysis as in openapi.yaml
// Non-2xx throws ApiError {status, code, message}. Network failure → ApiError {status: 0, code: 'network'}.
```

### `composables/useConversation.js`

Returns reactive state + actions; components only talk to this.

```js
const {
  messages,     // Ref<Message[]>
  stage,        // Ref<'start'|'extracting'|'review'|'analyzing'|'answered'|'error'>
  busy,         // Ref<boolean>
  language,     // Ref<string> (default 'en')
  analysis,     // Ref<Analysis|null>  latest response, drives DeadlineBanner
  redaction,    // Ref<{text, placeholders, mapping}|null>
  pendingQuestion, // Ref<string>  composer text before the letter is sent
  startWithFile,   // (file: File) → void
  startWithSample, // () → void
  toggleToken,     // (tokenIndex) → void  hide/reveal a word in the review bubble
  confirmRedaction,// () → void  calls /analyze
  ask,             // (question: string) → void  follow-up
  openChip,        // ('draft'|'glossary'|'sources') → void
  retry,           // () → void  repeat last failed action
  reset,           // () → void  new letter
} = useConversation()
```

`Message` (discriminated by `kind`):

```js
{ id, from: 'bot'|'me', kind: 'text',      text }
{ id, from: 'me',       kind: 'photo',     url /* object URL */, name }
{ id, from: 'bot',      kind: 'typing' }
{ id, from: 'bot',      kind: 'review',    tokens: [{ text, hidden, placeholder? }], confirmed: bool }
{ id, from: 'bot',      kind: 'analysis',  analysis }   // AnalysisAnswer renders the multi-bubble answer
{ id, from: 'bot',      kind: 'answer',    text }       // follow-up answer
{ id, from: 'bot',      kind: 'draft',     text /* placeholders filled */ }
{ id, from: 'bot',      kind: 'glossary',  items }
{ id, from: 'bot',      kind: 'sources',   items }
{ id, from: 'bot',      kind: 'error',     text, action: 'retry'|'retake' }
{ id, from: 'bot',      kind: 'actions',   actions: [{ id, label, primary? }] } // start buttons / chips
```

The review `tokens` split the redacted text into words and whitespace; the text sent to `/analyze` is rebuilt from tokens (hidden → placeholder or `[HIDDEN]`).

## Visual style

Warm chat background (#efeae2-ish), white bot bubbles, light green user bubbles, near-black primary buttons, pill chips, German terms highlighted (pale yellow, italic) next to translations. Large tap targets (≥ 44px), system font, safe-area insets for notched phones. Sticky header + banner, composer fixed at the bottom.

## Testing

- `vitest` for `redact.js`: on the MUSTER text, no `Mustermann`, `Musterstraße`, file number or IBAN survives; deadline dates and `Ausländerbehörde` survive; `fillPlaceholders(redact(t).text, mapping)` round-trips.
- Manual: full flow on a real phone against the Prism mock (MUSTER button + a camera photo).

## Not in v1

City dashboard, `.ics`, streaming, translated UI chrome, offline/PWA.
