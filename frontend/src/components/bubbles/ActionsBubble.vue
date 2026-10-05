<script setup>
import { computed } from 'vue'

const props = defineProps({
  actions: { type: Array, default: () => [] },
  active: Boolean,
  busy: Boolean,
})
defineEmits(['pick'])

const START = ['camera', 'upload', 'sample']
const isStart = computed(() => props.actions.some((a) => START.includes(a.id)))
const disabled = computed(() => !props.active || props.busy)
</script>

<template>
  <div class="chips" :class="{ col: isStart }" role="group">
    <button
      v-for="a in actions"
      :key="a.id"
      type="button"
      class="chip"
      :class="{ fill: a.primary, big: isStart, dashed: a.id === 'sample' }"
      :disabled="disabled"
      @click="$emit('pick', a.id)"
    >{{ a.label }}</button>
  </div>
</template>
