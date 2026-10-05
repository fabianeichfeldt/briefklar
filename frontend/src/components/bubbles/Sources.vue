<script setup>
defineProps({ items: { type: Array, default: () => [] } })
</script>

<template>
  <div class="bubble bot wide">
    <h4>🔗 Official pages</h4>
    <p v-if="!items.length" class="muted">No official page found for this letter.</p>
    <ul v-else class="src">
      <li v-for="(s, i) in items" :key="i">
        <a :href="s.url" target="_blank" rel="noopener noreferrer">{{ s.title }} ↗</a>
      </li>
    </ul>
  </div>
</template>
