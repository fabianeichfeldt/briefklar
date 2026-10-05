<script setup>
import { computed, reactive } from 'vue'
import { OFFICES } from '../../lib/labels.js'

const props = defineProps({
  analysis: { type: Object, required: true },
  rtl: Boolean,
})

const PILLS = { red: 'URGENT', yellow: 'SOON', green: 'INFO' }

const dir = computed(() => (props.rtl ? 'rtl' : 'ltr'))
const office = computed(() => OFFICES[props.analysis.office] || props.analysis.office)
const checked = reactive({})

function fmt(iso) {
  const [y, m, d] = String(iso).split('-').map(Number)
  if (!y) return iso
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(y, m - 1, d))
}
function left(n) {
  if (n < 0) return `overdue by ${-n} day${n === -1 ? '' : 's'}`
  if (n === 0) return 'today'
  return `in ${n} day${n === 1 ? '' : 's'}`
}
</script>

<template>
  <div class="bubble bot" :dir="dir">
    <div class="meta" dir="ltr">
      <span class="pill" :class="analysis.light">{{ PILLS[analysis.light] }}</span>
      <span class="muted">{{ office }}<template v-if="analysis.senderVerified"> ✓</template></span>
    </div>
    <p>{{ analysis.meaning }}</p>
    <p v-if="analysis.answer" style="margin-top: 8px"><b>💬 </b>{{ analysis.answer }}</p>
  </div>

  <div v-if="analysis.steps?.length || analysis.deadline || analysis.otherDates?.length" class="bubble bot" :dir="dir">
    <template v-if="analysis.steps?.length">
      <h4>✅ What to do</h4>
      <ul class="checklist">
        <li v-for="(s, i) in analysis.steps" :key="i">
          <button class="check" :class="{ done: checked[i] }" type="button" :aria-pressed="!!checked[i]" @click="checked[i] = !checked[i]">
            <span class="box" aria-hidden="true">{{ checked[i] ? '✓' : '' }}</span>
            <span class="label">{{ s }}</span>
          </button>
        </li>
      </ul>
    </template>
    <blockquote v-if="analysis.deadline?.sourceSentence" class="quote" dir="ltr" lang="de">
      📄 „{{ analysis.deadline.sourceSentence }}“
    </blockquote>
    <ul v-if="analysis.otherDates?.length" class="dates">
      <li v-for="(d, i) in analysis.otherDates" :key="i">
        <b>{{ fmt(d.date) }}</b> · {{ d.label }}
        <span class="muted">({{ left(d.daysLeft) }})</span>
      </li>
    </ul>
  </div>

  <div v-if="analysis.documents?.length" class="bubble bot" :dir="dir">
    <h4>🎒 Bring</h4>
    <ul class="list">
      <li v-for="(d, i) in analysis.documents" :key="i">{{ d }}</li>
    </ul>
  </div>

  <div v-if="analysis.uncertainties?.length" class="bubble bot warn" :dir="dir">
    <h4>⚠️ Not sure about</h4>
    <ul class="list">
      <li v-for="(u, i) in analysis.uncertainties" :key="i">{{ u }}</li>
    </ul>
    <p class="muted" style="margin-top: 6px">
      When in doubt, ask in person: at the office named in your letter, a Migrationsberatung or the Jobcenter counter.
    </p>
  </div>

  <div class="bubble bot note" dir="ltr">ⓘ {{ analysis.disclaimer }}<br />Not legal advice.</div>
</template>
