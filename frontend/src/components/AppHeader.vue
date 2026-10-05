<script setup>
import { LANGS } from '../lib/labels.js'

defineProps({ showNew: Boolean, showBack: Boolean, subtitle: { type: String, default: 'explains official letters' } })
const language = defineModel('language', { type: String, default: 'en' })
defineEmits(['new', 'back'])
</script>

<template>
  <header class="header">
    <button v-if="showBack" class="back-btn" type="button" aria-label="All letters" @click="$emit('back')">‹</button>
    <img v-if="!showBack" class="logo" src="/brand/briefklar-icon.png" alt="" aria-hidden="true">
    <div class="header-title">
      <img class="wordmark" src="/brand/briefklar-wordmark-on-blue.png" alt="Briefklar">
      <span>{{ subtitle }}</span>
    </div>
    <div class="header-actions">
      <button v-if="showNew" class="icon-btn" type="button" aria-label="New letter" title="New letter" @click="$emit('new')">＋</button>
      <select v-model="language" class="lang" aria-label="Language">
        <option v-for="[code, name] in LANGS" :key="code" :value="code">🌐 {{ name }}</option>
      </select>
    </div>
  </header>
</template>
