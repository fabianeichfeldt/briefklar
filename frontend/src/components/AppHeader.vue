<script setup>
defineProps({ showNew: Boolean, showBack: Boolean, subtitle: { type: String, default: 'explains official letters' } })
const language = defineModel('language', { type: String, default: 'en' })
defineEmits(['new', 'back'])

const LANGS = [
  ['en', 'English'],
  ['uk', 'Українська'],
  ['ar', 'العربية'],
  ['tr', 'Türkçe'],
  ['fa', 'فارسی'],
  ['ro', 'Română'],
]
</script>

<template>
  <header class="header">
    <button v-if="showBack" class="back-btn" type="button" aria-label="All letters" @click="$emit('back')">‹</button>
    <div v-if="!showBack" class="logo" aria-hidden="true">B</div>
    <div class="header-title">
      <b>Briefklar</b>
      <span>{{ subtitle }}</span>
    </div>
    <div class="header-actions">
      <button v-if="showNew" class="icon-btn" type="button" aria-label="New letter" @click="$emit('new')">＋ New</button>
      <select v-model="language" class="lang" aria-label="Language">
        <option v-for="[code, name] in LANGS" :key="code" :value="code">🌐 {{ name }}</option>
      </select>
    </div>
  </header>
</template>
