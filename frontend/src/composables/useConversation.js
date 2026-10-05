import { ref, watch } from 'vue'
import { extractText, overviewLetter, analyzeLetter, ApiError } from '../lib/api.js'
import { downscaleImage } from '../lib/image.js'
import { redact, fillPlaceholders, tokenize } from '../lib/redact.js'
import { SAMPLE_LETTER_TEXT } from '../lib/sample.js'
import { loadHistory, saveHistory, clearHistoryStorage, sanitizeMessage, refreshDays } from '../lib/history.js'

// Module-level singleton state: every useConversation() call shares it.
// Nothing is logged. Answered letters are saved to this browser's localStorage without
// photos or the placeholder mapping (see lib/history.js).
const messages = ref([])
const stage = ref('start')
const busy = ref(false)
const language = ref('en')
const analysis = ref(null)
const redaction = ref(null)
const pendingQuestion = ref('')
const history = ref(loadHistory()) // newest first
const currentId = ref(null) // id of the saved conversation being shown, null until first answer
const view = ref('list') // the letter list is the home screen
// On: the on-device redaction is sent straight away. Off: the user reviews it first.
const AUTO_REDACT_KEY = 'briefklar.autoRedact'
const autoRedact = ref(readSetting(AUTO_REDACT_KEY, true))
watch(autoRedact, (v) => writeSetting(AUTO_REDACT_KEY, v))

function readSetting(key, fallback) {
  try {
    const v = globalThis.localStorage?.getItem(key)
    return v === null || v === undefined ? fallback : JSON.parse(v)
  } catch {
    return fallback
  }
}
function writeSetting(key, value) {
  try {
    globalThis.localStorage?.setItem(key, JSON.stringify(value))
  } catch {}
}

let nextId = 1
let generation = 0 // bumped on reset so stale responses are ignored
let lastAction = null // () => Promise, re-run by retry()
let fullRequest = null // full /analyze, prefetched while the quick overview is shown
const objectUrls = []

const START_ACTIONS = [
  { id: 'camera', label: '📸 Take a photo', primary: true },
  { id: 'upload', label: '🖼️ Upload photo / PDF' },
  { id: 'sample', label: '🧪 Try a MUSTER letter' },
]
const DETAIL_CHIPS = [{ id: 'detail', label: '🔎 Explain in detail', primary: true }]
const RESULT_CHIPS = [
  { id: 'draft', label: '✉️ Reply in German' },
  { id: 'glossary', label: '📖 German words' },
  { id: 'sources', label: '🔗 Official pages' },
]

function push(msg) {
  const m = { id: nextId++, ...msg }
  messages.value.push(m)
  return m
}
function remove(id) {
  const i = messages.value.findIndex((m) => m.id === id)
  if (i >= 0) messages.value.splice(i, 1)
}
function removeActions() {
  messages.value = messages.value.filter((m) => m.kind !== 'actions')
}
function pushText(from, text) {
  return push({ from, kind: 'text', text })
}

function greet() {
  pushText('bot', 'Hi! I explain German official letters in your language. 👋')
  pushText(
    'bot',
    'Before your letter is explained, names and addresses are hidden on your phone. Your letters are saved only on this phone, without names, and you can delete them anytime.'
  )
  push({ from: 'bot', kind: 'actions', actions: START_ACTIONS })
}

function persist() {
  if (!analysis.value) return
  const now = new Date().toISOString()
  if (!currentId.value) currentId.value = `c${Date.now().toString(36)}`
  const prev = history.value.find((c) => c.id === currentId.value)
  const entry = {
    id: currentId.value,
    createdAt: prev?.createdAt ?? now,
    updatedAt: now,
    redactedText: redaction.value?.text ?? '',
    analysis: analysis.value,
    messages: messages.value.map(sanitizeMessage).filter(Boolean),
  }
  history.value = [entry, ...history.value.filter((c) => c.id !== entry.id)]
  saveHistory(history.value)
}

function openConversation(id) {
  const c = history.value.find((x) => x.id === id)
  if (!c) return
  clearState()
  currentId.value = c.id
  messages.value = c.messages.map((m) => ({
    ...m,
    id: nextId++,
    ...(m.kind === 'review' ? { explained: true } : {}), // saved chats were always answered
  }))
  analysis.value = refreshDays(c.analysis)
  // The mapping was never saved, so drafts keep their placeholders.
  redaction.value = { text: c.redactedText, placeholders: [], mapping: {} }
  push({ from: 'bot', kind: 'actions', actions: analysis.value.depth === 'overview' ? DETAIL_CHIPS : RESULT_CHIPS })
  stage.value = 'answered'
  view.value = 'chat'
}

function deleteConversation(id) {
  history.value = history.value.filter((c) => c.id !== id)
  saveHistory(history.value)
  if (currentId.value === id) reset()
}

function clearHistory() {
  history.value = []
  clearHistoryStorage()
  reset()
}

function showList() {
  if (busy.value) return
  view.value = 'list'
}

function reviewMessage() {
  return [...messages.value].reverse().find((m) => m.kind === 'review' && !m.confirmed)
}

// Runs fn behind a typing bubble; always removes the bubble. Errors become an error bubble.
async function withTyping(fn, retryable) {
  const gen = generation
  busy.value = true
  const typing = push({ from: 'bot', kind: 'typing' })
  lastAction = retryable
  try {
    await fn(gen)
  } catch (e) {
    if (gen !== generation) return
    const err = e instanceof ApiError ? e : new ApiError(0, 'unknown', 'Something went wrong.')
    stage.value = 'error'
    if (err.status === 422) {
      push({ from: 'bot', kind: 'error', text: err.message, action: 'retake' })
    } else if (err.status === 400) {
      push({ from: 'bot', kind: 'error', text: err.message, action: 'retry' })
    } else {
      push({ from: 'bot', kind: 'error', text: 'Something went wrong. Please try again.', action: 'retry' })
    }
  } finally {
    remove(typing.id)
    if (gen === generation) busy.value = false
  }
}

function showReview(text) {
  const result = redact(text)
  const mapping = result.mapping || {}
  redaction.value = { text: result.text, placeholders: result.placeholders, mapping }
  const tokens = tokenize(result.text).map((t) =>
    t.placeholder
      ? { text: t.text, hidden: true, placeholder: t.placeholder }
      : { text: t.text, hidden: false }
  )
  push({ from: 'bot', kind: 'review', tokens, confirmed: false, auto: autoRedact.value })
  stage.value = 'review'
}

// With auto-redact on, the review step is skipped and the redacted text is sent right away.
function autoConfirm() {
  if (autoRedact.value && stage.value === 'review') confirmRedaction()
}

async function runExtract(file, gen) {
  stage.value = 'extracting'
  const small = await downscaleImage(file)
  const res = await extractText(small)
  if (gen !== generation) return
  showReview(res.text)
}

function startWithFile(file) {
  if (busy.value || !file) return
  removeActions()
  if (file.type && file.type.startsWith('image/')) {
    const url = URL.createObjectURL(file)
    objectUrls.push(url)
    push({ from: 'me', kind: 'photo', url, name: file.name || 'photo' })
  } else {
    pushText('me', '📄 ' + (file.name || 'PDF'))
  }
  const run = () => withTyping((gen) => runExtract(file, gen), run).then(autoConfirm)
  run()
}

function startWithSample() {
  if (busy.value) return
  removeActions()
  pushText('me', '🧪 MUSTER letter')
  stage.value = 'extracting'
  showReview(SAMPLE_LETTER_TEXT)
  autoConfirm()
}

function toggleToken(index) {
  const msg = reviewMessage()
  const tok = msg && msg.tokens[index]
  if (!tok || !tok.text.trim()) return
  const map = (redaction.value && redaction.value.mapping) || {}
  if (tok.placeholder) {
    if (tok.hidden) {
      tok.text = map[tok.placeholder] ?? tok.placeholder
      tok.hidden = false
    } else {
      tok.text = tok.placeholder
      tok.hidden = true
    }
  } else if (tok.hidden) {
    tok.text = tok.original
    tok.hidden = false
  } else {
    tok.original = tok.text
    tok.text = '[HIDDEN]'
    tok.hidden = true
  }
}

function runAnalyze(question, gen) {
  stage.value = 'analyzing'
  return analyzeLetter({
    text: redaction.value.text,
    language: language.value,
    question: question || null,
  }).then((res) => {
    if (gen !== generation) return null
    analysis.value = res
    return res
  })
}

// Starts the full analysis in the background, so "Explain in detail" is usually instant.
// A failed request is forgotten, so the next click fetches it again.
function fetchFull(question) {
  const p = analyzeLetter({ text: redaction.value.text, language: language.value, question: question || null })
  fullRequest = p
  p.catch(() => { if (fullRequest === p) fullRequest = null })
  return p
}

function confirmRedaction() {
  const msg = reviewMessage()
  if (!msg || busy.value) return
  msg.confirmed = true
  const text = msg.tokens.map((t) => t.text).join('')
  redaction.value = { ...redaction.value, text } // later requests reuse the user's final choice
  const question = pendingQuestion.value.trim()
  pendingQuestion.value = ''
  if (question) pushText('me', question)
  let shown = false
  const run = () =>
    withTyping(async (gen) => {
      stage.value = 'analyzing'
      if (!fullRequest) fetchFull(question)
      const res = await overviewLetter({ text: redaction.value.text, language: language.value })
      if (gen !== generation) return
      analysis.value = res
      msg.explained = true // folds the redaction preview
      push({ from: 'bot', kind: 'overview', analysis: res })
      if (!question) push({ from: 'bot', kind: 'actions', actions: DETAIL_CHIPS })
      stage.value = 'answered'
      shown = true
      persist()
    }, run).then(() => { if (shown && question) answerPending() })
  run()
}

// The question typed before the upload is answered by the prefetched full analysis.
function answerPending() {
  const run = () =>
    withTyping(async (gen) => {
      stage.value = 'asking'
      const res = await (fullRequest || fetchFull(null))
      if (gen !== generation) return
      push({ from: 'bot', kind: 'answer', text: res.answer || res.meaning })
      push({ from: 'bot', kind: 'actions', actions: DETAIL_CHIPS })
      stage.value = 'answered'
      persist()
    }, run)
  run()
}

function explainInDetail() {
  if (busy.value || !redaction.value) return
  const run = () =>
    withTyping(async (gen) => {
      stage.value = 'detailing'
      const res = analysis.value?.depth === 'full' ? analysis.value : await (fullRequest || fetchFull(null))
      if (gen !== generation) return
      analysis.value = res
      push({ from: 'bot', kind: 'analysis', analysis: res })
      push({ from: 'bot', kind: 'actions', actions: RESULT_CHIPS })
      stage.value = 'answered'
      persist()
    }, run)
  run()
}

function ask(question) {
  const q = (question || '').trim()
  if (!q || busy.value) return
  if (!redaction.value) {
    pendingQuestion.value = q
    return
  }
  pushText('me', q)
  const run = () =>
    withTyping(async (gen) => {
      const res = await runAnalyze(q, gen)
      if (!res) return
      push({ from: 'bot', kind: 'answer', text: res.answer || res.meaning })
      stage.value = 'answered'
      persist()
    }, run)
  run()
}

function openChip(id) {
  const a = analysis.value
  if (!a) return
  if (id === 'detail') return explainInDetail()
  if (id === 'draft') {
    const map = redaction.value && redaction.value.mapping
    const text = map ? fillPlaceholders(a.draftDe || '', map) : a.draftDe || ''
    push({ from: 'bot', kind: 'draft', text, raw: a.draftDe || '' })
  } else if (id === 'glossary') {
    push({ from: 'bot', kind: 'glossary', items: a.glossary || [] })
  } else if (id === 'sources') {
    push({ from: 'bot', kind: 'sources', items: a.sources || [] })
  }
  persist()
}

function retry() {
  if (busy.value || !lastAction) return
  const last = [...messages.value].reverse().find((m) => m.kind === 'error')
  if (last) remove(last.id)
  lastAction()
}

function clearState() {
  generation++
  objectUrls.splice(0).forEach((u) => URL.revokeObjectURL(u))
  messages.value = []
  stage.value = 'start'
  busy.value = false
  analysis.value = null
  redaction.value = null
  pendingQuestion.value = ''
  lastAction = null
  fullRequest = null
  currentId.value = null
}

// Starts a fresh letter in the chat view.
function reset() {
  clearState()
  view.value = 'chat'
  greet()
}

greet()

export function useConversation() {
  return {
    messages,
    stage,
    busy,
    language,
    autoRedact,
    analysis,
    redaction,
    pendingQuestion,
    startWithFile,
    startWithSample,
    toggleToken,
    confirmRedaction,
    ask,
    openChip,
    retry,
    reset,
    history,
    currentId,
    view,
    openConversation,
    deleteConversation,
    clearHistory,
    showList,
  }
}
