<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useConversation } from '../composables/useConversation.js'
import RedactionPreview from './bubbles/RedactionPreview.vue'
import AnalysisAnswer from './bubbles/AnalysisAnswer.vue'
import DraftDe from './bubbles/DraftDe.vue'
import Glossary from './bubbles/Glossary.vue'
import Sources from './bubbles/Sources.vue'
import ActionsBubble from './bubbles/ActionsBubble.vue'
import ErrorBubble from './bubbles/ErrorBubble.vue'
import { langName } from '../lib/labels.js'

const emit = defineEmits(['camera', 'upload'])
const {
  messages, stage, busy, language,
  toggleToken, confirmRedaction, openChip, retry, startWithSample,
} = useConversation()

const el = ref(null)
const rtl = computed(() => language.value === 'ar' || language.value === 'fa')
const typingLabel = computed(() => {
  if (stage.value === 'extracting') return 'Reading your letter'
  if (stage.value === 'analyzing') return `Explaining it in ${langName(language.value)}`
  return 'Looking at your question'
})

const lastActionsId = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    if (messages.value[i].kind === 'actions') return messages.value[i].id
  }
  return null
})
const lastId = computed(() => messages.value[messages.value.length - 1]?.id)

function toBottom() {
  nextTick(() => {
    if (el.value) el.value.scrollTo({ top: el.value.scrollHeight, behavior: 'smooth' })
  })
}
watch(() => [messages.value.length, lastId.value], toBottom, { flush: 'post' })
// A reopened letter starts at its latest message, like a chat app.
onMounted(() => nextTick(() => requestAnimationFrame(() => { if (el.value) el.value.scrollTop = el.value.scrollHeight })))

function scrollToAnalysis() {
  const nodes = el.value?.querySelectorAll('[data-kind="analysis"]')
  const node = nodes && nodes[nodes.length - 1]
  node?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
defineExpose({ scrollToAnalysis })

function onAction(id) {
  if (id === 'camera') emit('camera')
  else if (id === 'upload') emit('upload')
  else if (id === 'sample') startWithSample()
  else openChip(id)
}
</script>

<template>
  <main ref="el" class="thread" aria-live="polite">
    <div v-for="m in messages" :key="m.id" class="row" :class="m.from" :data-kind="m.kind">
      <div v-if="m.kind === 'text'" class="bubble" :class="m.from" dir="auto" style="white-space: pre-line">{{ m.text }}</div>

      <div v-else-if="m.kind === 'photo'" class="bubble me photo">
        <img :src="m.url" :alt="m.name || 'Your letter'" />
      </div>

      <div v-else-if="m.kind === 'typing'" class="bubble bot typing" role="status">
        <span class="dots" aria-hidden="true"><i /><i /><i /></span>
        <span class="typing-label">{{ typingLabel }}…</span>
      </div>

      <RedactionPreview
        v-else-if="m.kind === 'review'"
        :message="m"
        :interactive="stage === 'review' && !busy"
        :scanning="stage === 'analyzing' && m.confirmed"
        @toggle="toggleToken"
        @confirm="confirmRedaction"
      />

      <AnalysisAnswer v-else-if="m.kind === 'analysis'" :analysis="m.analysis" :rtl="rtl" />

      <div v-else-if="m.kind === 'answer'" class="bubble bot" :dir="rtl ? 'rtl' : 'ltr'">{{ m.text }}</div>

      <DraftDe v-else-if="m.kind === 'draft'" :text="m.text" />
      <Glossary v-else-if="m.kind === 'glossary'" :items="m.items" :rtl="rtl" />
      <Sources v-else-if="m.kind === 'sources'" :items="m.items" />

      <ErrorBubble
        v-else-if="m.kind === 'error'"
        :message="m"
        :active="m.id === lastId && !busy"
        @retry="retry"
        @retake="emit('camera')"
      />

      <ActionsBubble
        v-else-if="m.kind === 'actions'"
        :actions="m.actions"
        :active="m.id === lastActionsId"
        :busy="busy"
        @pick="onAction"
      />
    </div>
  </main>
</template>
