<script setup>
import { computed } from 'vue'

const props = defineProps({ analysis: { type: Object, required: true } })
defineEmits(['select'])

function fmt(iso) {
  const [y, m, d] = String(iso).split('-').map(Number)
  if (!y) return iso
  return new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }).format(new Date(y, m - 1, d))
}

// { big, unit } for the number column; null when there is no deadline.
const count = computed(() => {
  const n = props.analysis.deadline?.daysLeft
  if (n == null) return null
  if (n < 0) return { big: -n, unit: `day${n === -1 ? '' : 's'} overdue` }
  if (n === 0) return { big: 'Today', unit: 'last day' }
  return { big: n, unit: `day${n === 1 ? '' : 's'} left` }
})

const noDeadline = computed(() => {
  const a = props.analysis
  return a.light === 'yellow' && a.lightReason ? `⚠️ ${a.lightReason}` : '✓ No deadline found'
})
</script>

<template>
  <button class="ticket" :class="analysis.light" type="button" @click="$emit('select')">
    <template v-if="count">
      <span class="ticket-count">
        <span :key="analysis.deadline.date" class="ticket-num mark swipe" :class="analysis.light">{{ count.big }}</span>
        <span class="ticket-unit">{{ count.unit }}</span>
      </span>
      <span class="ticket-info">
        <b>{{ analysis.deadline.label }}</b>
        <span>{{ fmt(analysis.deadline.date) }}</span>
      </span>
    </template>
    <span v-else class="ticket-info"><b>{{ noDeadline }}</b></span>
    <span class="chev" aria-hidden="true">›</span>
  </button>
</template>
