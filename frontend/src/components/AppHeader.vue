<script setup>
import { ref } from 'vue'
import { LANGS } from '../lib/labels.js'

defineProps({ showNew: Boolean, showBack: Boolean, subtitle: { type: String, default: 'explains official letters' } })
const language = defineModel('language', { type: String, default: 'en' })
const autoRedact = defineModel('autoRedact', { type: Boolean, default: true })
const settingsOpen = ref(false)
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
      <button class="icon-btn" type="button" aria-label="Settings" title="Settings" :aria-expanded="settingsOpen" @click="settingsOpen = !settingsOpen">⚙︎</button>
    </div>
    <div v-if="settingsOpen" class="settings" role="dialog" aria-label="Settings">
      <label class="setting">
        <span>
          <b>Auto-redact</b>
          <span class="muted">{{ autoRedact
            ? 'Names and addresses are hidden on your phone and the letter is explained right away.'
            : 'You check the hidden words yourself before anything is sent.' }}</span>
        </span>
        <input v-model="autoRedact" class="switch" type="checkbox" role="switch">
      </label>
    </div>
  </header>
</template>
