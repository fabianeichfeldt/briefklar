<script setup>
import { computed, ref } from 'vue'
import { useConversation } from './composables/useConversation.js'
import AppHeader from './components/AppHeader.vue'
import DeadlineBanner from './components/DeadlineBanner.vue'
import ChatThread from './components/ChatThread.vue'
import Composer from './components/Composer.vue'

const { stage, language, analysis, startWithFile, reset } = useConversation()

const cameraInput = ref(null)
const uploadInput = ref(null)
const thread = ref(null)

const showNew = computed(() => stage.value !== 'start')

function openCamera() { cameraInput.value?.click() }
function openUpload() { uploadInput.value?.click() }

function onFile(e) {
  const file = e.target.files?.[0]
  e.target.value = '' // allow picking the same file again
  if (!file) return
  if (stage.value === 'review' || stage.value === 'answered') reset()
  startWithFile(file)
}
</script>

<template>
  <div class="app">
    <AppHeader v-model:language="language" :show-new="showNew" @new="reset" />
    <DeadlineBanner v-if="analysis" :analysis="analysis" @select="thread?.scrollToAnalysis()" />
    <ChatThread ref="thread" @camera="openCamera" @upload="openUpload" />
    <Composer @camera="openCamera" />

    <input ref="cameraInput" class="sr-only" type="file" accept="image/*" capture="environment" tabindex="-1" aria-hidden="true" @change="onFile" />
    <input ref="uploadInput" class="sr-only" type="file" accept="image/*,application/pdf" tabindex="-1" aria-hidden="true" @change="onFile" />
  </div>
</template>
