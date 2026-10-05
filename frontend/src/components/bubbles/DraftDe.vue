<script setup>
import { ref, onBeforeUnmount } from 'vue'

const props = defineProps({ text: { type: String, default: '' } })
const copied = ref(false)
let timer

async function copy() {
  try {
    await navigator.clipboard.writeText(props.text)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = props.text
    document.body.appendChild(ta)
    ta.select()
    try { document.execCommand('copy') } catch { /* ignore */ }
    ta.remove()
  }
  copied.value = true
  clearTimeout(timer)
  timer = setTimeout(() => (copied.value = false), 2000)
}
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <div class="bubble bot wide">
    <h4>✉️ Reply in German</h4>
    <div class="paper" dir="ltr" lang="de">{{ text }}</div>
    <button class="chip copy" :class="{ fill: copied }" type="button" @click="copy">
      {{ copied ? 'Copied ✓' : '📋 Copy' }}
    </button>
  </div>
</template>
