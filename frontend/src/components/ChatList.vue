<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useConversation } from '../composables/useConversation.js'
import { officeName, LETTER_TYPES } from '../lib/labels.js'
import { refreshDays } from '../lib/history.js'

const emit = defineEmits(['new', 'camera', 'upload'])
const { history, openConversation, deleteConversation, clearHistory, reset, startWithSample, language } = useConversation()

function trySample() {
  reset()
  startWithSample()
}

const OFFICE_ICONS = {
  auslaenderbehoerde: '🛂', jobcenter: '💼', sozialamt: '🤝', buergeramt: '🏛️', kita_schule: '🎒',
  finanzamt: '🧾', familienkasse: '👨‍👩‍👧', rundfunkbeitrag: '📻',
}

function lastText(c) {
  const m = [...c.messages].reverse().find((x) => x.kind === 'answer' || (x.kind === 'text' && x.from === 'me'))
  if (m && m.kind === 'answer') return m.text
  if (m && m.from === 'me' && !m.text.startsWith('📷') && !m.text.startsWith('🧪')) return `You: ${m.text}`
  return c.analysis.meaning
}

function when(iso) {
  const d = new Date(iso)
  const today = new Date()
  if (d.toDateString() === today.toDateString()) {
    return new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit' }).format(d)
  }
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' }).format(d)
}

function badge(a) {
  const n = a.deadline?.daysLeft
  if (n == null) return a.light === 'green' ? '✓' : ''
  if (n < 0) return 'overdue'
  if (n === 0) return 'today'
  return `${n}d`
}

const rows = computed(() =>
  history.value.map((c) => {
    const a = refreshDays(c.analysis)
    return {
      id: c.id,
      icon: OFFICE_ICONS[a.office] || '✉️',
      title: officeName(a.office),
      type: LETTER_TYPES[a.letterType] || '',
      preview: lastText(c),
      when: when(c.updatedAt),
      light: a.light,
      badge: badge(a),
    }
  })
)

// Most urgent upcoming deadline across saved letters, for the list heading.
const next = computed(() => {
  let best = null
  for (const c of history.value) {
    const a = refreshDays(c.analysis)
    const n = a.deadline?.daysLeft
    if (n == null || n < 0) continue
    if (!best || n < best.days) best = { days: n, office: officeName(a.office) }
  }
  return best
})

// Hero: the German word on the letter, translated into each demo language in turn.
const WORDS = [
  ['en', 'Deadline'], ['uk', 'Кінцевий термін'], ['ar', 'الموعد النهائي'],
  ['tr', 'Son tarih'], ['fa', 'مهلت'], ['ro', 'Termen limită'],
]
const wordIdx = ref(Math.max(0, WORDS.findIndex(([c]) => c === language.value)))
const word = computed(() => WORDS[wordIdx.value])
let wordTimer
onMounted(() => {
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
  wordTimer = setInterval(() => (wordIdx.value = (wordIdx.value + 1) % WORDS.length), 2400)
})
onBeforeUnmount(() => clearInterval(wordTimer))

function confirmDelete(id) {
  if (confirm('Delete this letter from this phone?')) deleteConversation(id)
}
function confirmClear() {
  if (confirm('Delete all letters from this phone?')) clearHistory()
}
</script>

<template>
  <main class="letters" :class="{ hero: !rows.length }">
    <template v-if="rows.length">
      <section class="letters-head">
        <h1>Your letters</h1>
        <p v-if="next">Next deadline in <b>{{ next.days === 0 ? 'less than a day' : `${next.days} day${next.days === 1 ? '' : 's'}` }}</b>, {{ next.office }}</p>
        <p v-else>No open deadlines.</p>
      </section>

      <div class="sheet">
        <ul class="lrows">
          <li v-for="r in rows" :key="r.id" class="lrow">
            <button class="lrow-main" type="button" @click="openConversation(r.id)">
              <span class="avatar" :class="r.light" aria-hidden="true">{{ r.icon }}</span>
              <span class="lrow-body">
                <span class="lrow-top">
                  <b class="lrow-title">{{ r.title }}</b>
                  <span class="lrow-when">{{ r.when }}</span>
                </span>
                <span v-if="r.type" class="lrow-type">{{ r.type }}</span>
                <span class="lrow-bottom">
                  <span class="lrow-preview">{{ r.preview }}</span>
                  <span v-if="r.badge" class="lrow-badge mark" :class="r.light">{{ r.badge }}</span>
                </span>
              </span>
            </button>
            <button class="lrow-del" type="button" :aria-label="`Delete ${r.title} letter`" @click="confirmDelete(r.id)">🗑️</button>
          </li>
        </ul>
        <p class="letters-note">🔒 Saved only on this phone, without names or photos.</p>
        <button class="clear-all" type="button" @click="confirmClear">Delete all letters</button>
      </div>

      <button class="fab" type="button" aria-label="New letter" @click="emit('new')">📸<span>New letter</span></button>
    </template>

    <div v-else class="letters-empty">
      <div class="hero-art" aria-hidden="true">
        <div class="hero-letter">
          <span class="hl-from">Stadt Nürnberg · Ausländerbehörde</span>
          <span class="hl-line" style="width: 78%" />
          <span class="hl-line" style="width: 56%" />
          <span class="hl-frist"><span class="mark swipe">Frist: 13.10.2026</span></span>
          <span class="hl-tr">
            <Transition name="word" mode="out-in">
              <span :key="word[0]" :lang="word[0]" dir="auto">↳ {{ word[1] }}</span>
            </Transition>
          </span>
          <span class="hl-line" style="width: 88%" />
          <span class="hl-line" style="width: 64%" />
          <span class="hl-line" style="width: 40%" />
          <img class="stamp" src="/brand/briefklar-letter-check.svg" alt="">
        </div>
      </div>
      <h1>Got a letter from a German office?</h1>
      <p>Photograph it. You get a plain explanation in your language, every deadline, what to do and a reply in German.</p>
      <button class="empty-primary" type="button" @click="emit('camera')">📸 Photograph a letter</button>
      <div class="empty-row">
        <button class="empty-secondary" type="button" @click="emit('upload')"><span aria-hidden="true">🖼️</span>Upload photo / PDF</button>
        <button class="empty-secondary" type="button" @click="trySample"><span aria-hidden="true">🧪</span>Try a MUSTER letter</button>
      </div>
      <p class="empty-hint">🔒 Saved only on this phone, without names or photos.</p>
    </div>
  </main>
</template>
