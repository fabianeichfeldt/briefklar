<script setup>
defineProps({ message: { type: Object, required: true }, active: Boolean })
defineEmits(['retry', 'retake'])
</script>

<template>
  <div class="bubble bot err">
    <p>{{ message.text }}</p>
  </div>
  <div class="chips">
    <button v-if="message.action === 'retake'" class="chip fill" type="button" :disabled="!active" @click="$emit('retake')">📸 Retake</button>
    <button v-else class="chip fill" type="button" :disabled="!active" @click="$emit('retry')">↻ Try again</button>
  </div>
</template>
