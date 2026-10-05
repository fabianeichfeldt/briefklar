<script setup>
import { computed } from 'vue'

const props = defineProps({
  message: { type: Object, required: true },
  interactive: Boolean, // stage === 'review' and not confirmed
  scanning: Boolean, // the redacted text is being explained right now
})
const emit = defineEmits(['toggle', 'confirm'])

const hiddenCount = computed(() => props.message.tokens.filter((t) => t.hidden).length)
const live = computed(() => props.interactive && !props.message.confirmed)

function isWord(t) {
  return /\S/.test(t.text)
}
function label(t) {
  return t.hidden ? t.placeholder || '[HIDDEN]' : t.text
}
</script>

<template>
  <div class="bubble bot wide">
    <p>
      ✅ I read your letter. This is exactly what I'll send to the AI.
      <b>Violet bars are hidden</b><template v-if="live">, tap any word to hide or show it</template>.
    </p>
    <div class="paper" :class="{ readonly: !live, scanning }" dir="ltr" style="margin-top: 8px">
      <template v-for="(t, i) in message.tokens" :key="i">
        <span
          v-if="isWord(t)"
          class="tok"
          :class="{ hid: t.hidden, live }"
          :role="live ? 'button' : undefined"
          :tabindex="live ? 0 : undefined"
          @click="live && emit('toggle', i)"
          @keydown.enter.prevent="live && emit('toggle', i)"
          @keydown.space.prevent="live && emit('toggle', i)"
        >{{ label(t) }}</span>
        <template v-else>{{ t.text }}</template>
      </template>
    </div>
    <div class="muted" style="margin-top: 6px">
      {{ hiddenCount }} item{{ hiddenCount === 1 ? '' : 's' }} hidden. Dates and amounts are kept.
    </div>
  </div>
  <div v-if="live" class="chips" style="margin-top: 2px">
    <button class="chip fill" type="button" @click="emit('confirm')">✨ Looks good, explain it</button>
  </div>
</template>
