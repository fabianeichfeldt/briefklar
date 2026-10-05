import { ref } from 'vue'
import { extractText, analyzeLetter, ApiError } from '../lib/api.js'
import { downscaleImage } from '../lib/image.js'
import { redact, fillPlaceholders, tokenize } from '../lib/redact.js'
import { SAMPLE_LETTER_TEXT } from '../lib/sample.js'

// Module-level singleton state: every useConversation() call shares it.
// Letter content lives only in memory; nothing is logged.
const messages = ref([])
const stage = ref('start')
const busy = ref(false)
const language = ref('en')
const analysis = ref(null)
const redaction = ref(null)
const pendingQuestion = ref('')

let nextId = 1
let generation = 0 // bumped on reset so stale responses are ignored
let lastAction = null // () => Promise, re-run by retry()
const objectUrls = []

const START_ACTIONS = [
  { id: 'camera', label: '📸 Take a photo', primary: true },
  { id: 'upload', label: '🖼️ Upload photo / PDF' },
  { id: 'sample', label: '🧪 Try a MUSTER letter' },
]
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
    'Your letter is processed in memory only and nothing is stored. Names and addresses are hidden on your phone before the text is analysed.'
  )
  push({ from: 'bot', kind: 'actions', actions: START_ACTIONS })
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
  push({ from: 'bot', kind: 'review', tokens, confirmed: false })
  stage.value = 'review'
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
  const run = () => withTyping((gen) => runExtract(file, gen), run)
  run()
}

function startWithSample() {
  if (busy.value) return
  removeActions()
  pushText('me', '🧪 MUSTER letter')
  stage.value = 'extracting'
  showReview(SAMPLE_LETTER_TEXT)
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

function confirmRedaction() {
  const msg = reviewMessage()
  if (!msg || busy.value) return
  msg.confirmed = true
  const text = msg.tokens.map((t) => t.text).join('')
  redaction.value = { ...redaction.value, text } // later requests reuse the user's final choice
  const question = pendingQuestion.value.trim()
  pendingQuestion.value = ''
  if (question) pushText('me', question)
  const run = () =>
    withTyping(async (gen) => {
      const res = await runAnalyze(question, gen)
      if (!res) return
      push({ from: 'bot', kind: 'analysis', analysis: res })
      push({ from: 'bot', kind: 'actions', actions: RESULT_CHIPS })
      stage.value = 'answered'
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
    }, run)
  run()
}

function openChip(id) {
  const a = analysis.value
  if (!a) return
  if (id === 'draft') {
    const map = redaction.value && redaction.value.mapping
    const text = map ? fillPlaceholders(a.draftDe || '', map) : a.draftDe || ''
    push({ from: 'bot', kind: 'draft', text })
  } else if (id === 'glossary') {
    push({ from: 'bot', kind: 'glossary', items: a.glossary || [] })
  } else if (id === 'sources') {
    push({ from: 'bot', kind: 'sources', items: a.sources || [] })
  }
}

function retry() {
  if (busy.value || !lastAction) return
  const last = [...messages.value].reverse().find((m) => m.kind === 'error')
  if (last) remove(last.id)
  lastAction()
}

function reset() {
  generation++
  objectUrls.splice(0).forEach((u) => URL.revokeObjectURL(u))
  messages.value = []
  stage.value = 'start'
  busy.value = false
  analysis.value = null
  redaction.value = null
  pendingQuestion.value = ''
  lastAction = null
  greet()
}

greet()

export function useConversation() {
  return {
    messages,
    stage,
    busy,
    language,
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
  }
}
