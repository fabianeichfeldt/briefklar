<script setup>
defineProps({ items: { type: Array, default: () => [] }, rtl: Boolean })
</script>

<template>
  <div class="bubble bot wide">
    <h4>📖 German words</h4>
    <ul class="gloss">
      <li v-for="(g, i) in items" :key="i">
        <bdi class="de" dir="ltr" lang="de">{{ g.term }}</bdi>
        <span :dir="rtl ? 'rtl' : 'ltr'"> → {{ g.explanation }}</span>
      </li>
    </ul>
  </div>
</template>
