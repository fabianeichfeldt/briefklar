<script setup>
import { computed } from 'vue'
import { OFFICES } from '../../lib/labels.js'

// Quick first look from POST /overview: what it is, how urgent, do I have to act, by when.
const props = defineProps({
  analysis: { type: Object, required: true },
  rtl: Boolean,
})

const PILLS = { red: 'Urgent', yellow: 'Soon', green: 'For your information' }

const dir = computed(() => (props.rtl ? 'rtl' : 'ltr'))
const office = computed(() => OFFICES[props.analysis.office] || props.analysis.office)
const act = computed(() => props.analysis.actionNeeded ?? props.analysis.steps?.length > 0)

function fmt(iso) {
  const [y, m, d] = String(iso).split('-').map(Number)
  if (!y) return iso
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' }).format(new Date(y, m - 1, d))
}
const due = computed(() => {
  const d = props.analysis.deadline
  if (!d) return null
  const n = d.daysLeft
  const when = n < 0 ? `overdue by ${-n} day${n === -1 ? '' : 's'}` : n === 0 ? 'today' : `${n} day${n === 1 ? '' : 's'} left`
  return { when, label: d.label, date: fmt(d.date) }
})
</script>

<template>
  <div class="bubble bot lead" :dir="dir">
    <div class="meta" dir="ltr">
      <span class="mark swipe" :class="analysis.light">{{ PILLS[analysis.light] }}</span>
      <span class="office">{{ office }}<span v-if="analysis.senderVerified" class="verified" title="Sender checked against the official list"> ✓</span></span>
    </div>
    <p class="meaning">{{ analysis.meaning }}</p>
    <ul class="glance">
      <li>
        <span aria-hidden="true">{{ act ? '👉' : '✓' }}</span>
        <span><b>{{ act ? 'You need to act' : 'Nothing to do' }}</b><template v-if="act && analysis.steps?.[0]">: {{ analysis.steps[0] }}</template></span>
      </li>
      <li v-if="due">
        <span aria-hidden="true">⏳</span>
        <span><b>{{ due.when }}</b>: {{ due.label }} (<bdi>{{ due.date }}</bdi>)</span>
      </li>
      <li v-if="analysis.uncertainties?.length" class="muted">
        <span aria-hidden="true">⚠️</span>
        <span>Some details are unclear. Check them in the detailed explanation or ask in person.</span>
      </li>
    </ul>
  </div>
  <div class="bubble bot note" dir="ltr">ⓘ {{ analysis.disclaimer }}<br />Not legal advice.</div>
</template>

<style scoped>
.glance { list-style: none; margin: 12px 0 0; padding: 0; font-size: 15px; }
.glance li { display: flex; gap: 10px; padding: 7px 0; border-top: 1px solid var(--line); }
</style>
