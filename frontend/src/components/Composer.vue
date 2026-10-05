<script setup>
import { computed, ref } from 'vue'
import { useConversation } from '../composables/useConversation.js'

defineEmits(['camera'])
const { stage, busy, pendingQuestion, ask } = useConversation()

const followUp = ref('')
const answered = computed(() => stage.value === 'answered')

const model = computed({
  get: () => (answered.value ? followUp.value : pendingQuestion.value),
  set: (v) => {
    if (answered.value) followUp.value = v
    else pendingQuestion.value = v
  },
})

const canSend = computed(() => answered.value && !busy.value && followUp.value.trim().length > 0)

function send() {
  if (!canSend.value) return
  const q = followUp.value.trim()
  followUp.value = ''
  ask(q)
}
</script>

<template>
  <form class="composer" @submit.prevent="send">
    <button class="round light" type="button" :disabled="busy" aria-label="Take a photo" @click="$emit('camera')">📸</button>
    <input
      v-model="model"
      dir="auto"
      type="text"
      enterkeyhint="send"
      autocomplete="off"
      :disabled="busy"
      :placeholder="answered ? 'Ask about your letter…' : 'Optional: your question…'"
      :aria-label="answered ? 'Ask about your letter' : 'Optional question'"
    />
    <button class="round" type="submit" :disabled="!canSend" aria-label="Send">➤</button>
  </form>
</template>
