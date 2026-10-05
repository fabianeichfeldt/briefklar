<script setup>
import { computed } from 'vue'

const props = defineProps({ analysis: { type: Object, required: true } })
defineEmits(['select'])

function fmt(iso) {
  const [y, m, d] = String(iso).split('-').map(Number)
  if (!y) return iso
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' }).format(new Date(y, m - 1, d))
}

const text = computed(() => {
  const a = props.analysis
  const d = a.deadline
  if (!d) {
    return a.light === 'yellow' && a.lightReason ? `⚠️ ${a.lightReason}` : '✓ No deadline found'
  }
  const n = d.daysLeft
  let head
  if (n < 0) head = `Overdue by ${-n} day${n === -1 ? '' : 's'}`
  else if (n === 0) head = 'Due today'
  else head = `${n} day${n === 1 ? '' : 's'} left`
  return `⏰ ${head} · ${d.label} · ${fmt(d.date)}`
})
</script>

<template>
  <button class="banner" :class="analysis.light" type="button" @click="$emit('select')">
    <span>{{ text }}</span>
    <span class="chev" aria-hidden="true">›</span>
  </button>
</template>
