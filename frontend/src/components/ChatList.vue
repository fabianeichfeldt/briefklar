<script setup>
import { computed } from 'vue'
import { useConversation } from '../composables/useConversation.js'
import { officeName, LETTER_TYPES } from '../lib/labels.js'
import { refreshDays } from '../lib/history.js'

const emit = defineEmits(['new', 'camera', 'upload'])
const { history, openConversation, deleteConversation, clearHistory, reset, startWithSample } = useConversation()

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

function confirmDelete(id) {
  if (confirm('Delete this letter from this phone?')) deleteConversation(id)
}
function confirmClear() {
  if (confirm('Delete all letters from this phone?')) clearHistory()
}
</script>

<template>
  <main class="letters">
    <p class="letters-note">🔒 Saved only on this phone, without names or photos.</p>

    <ul v-if="rows.length" class="lrows">
      <li v-for="r in rows" :key="r.id" class="lrow">
        <button class="lrow-main" type="button" @click="openConversation(r.id)">
          <span class="avatar" :class="r.light" aria-hidden="true">{{ r.icon }}</span>
          <span class="lrow-body">
            <span class="lrow-top">
              <b class="lrow-title">{{ r.title }}<span v-if="r.type" class="lrow-type"> · {{ r.type }}</span></b>
              <span class="lrow-when">{{ r.when }}</span>
            </span>
            <span class="lrow-bottom">
              <span class="lrow-preview">{{ r.preview }}</span>
              <span v-if="r.badge" class="lrow-badge" :class="r.light">{{ r.badge }}</span>
            </span>
          </span>
        </button>
        <button class="lrow-del" type="button" :aria-label="`Delete ${r.title} letter`" @click="confirmDelete(r.id)">🗑️</button>
      </li>
    </ul>

    <div v-else class="letters-empty">
      <div class="empty-icon" aria-hidden="true">✉️</div>
      <h1>Understand letters from German offices</h1>
      <p>Take a photo of a letter. You get a plain explanation in your language, every deadline, what to do and a German reply.</p>
      <button class="empty-primary" type="button" @click="emit('camera')">📸 Photograph a letter</button>
      <button class="empty-secondary" type="button" @click="emit('upload')">🖼️ Upload photo / PDF</button>
      <button class="empty-secondary dashed" type="button" @click="trySample">🧪 Try a MUSTER letter</button>
      <p class="empty-hint">Your letters will appear here.</p>
    </div>

    <button v-if="rows.length" class="clear-all" type="button" @click="confirmClear">Delete all letters</button>

    <button v-if="rows.length" class="fab" type="button" aria-label="New letter" @click="emit('new')">📸<span>New letter</span></button>
  </main>
</template>
