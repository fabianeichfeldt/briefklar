<script setup>
import { computed, ref } from 'vue'
import { useConversation } from './composables/useConversation.js'
import AppHeader from './components/AppHeader.vue'
import DeadlineBanner from './components/DeadlineBanner.vue'
import ChatThread from './components/ChatThread.vue'
import Composer from './components/Composer.vue'
import ChatList from './components/ChatList.vue'

const { stage, language, autoRedact, analysis, startWithFile, reset, view, history, showList } = useConversation()

const cameraInput = ref(null)
const uploadInput = ref(null)
const thread = ref(null)

const showNew = computed(() => view.value === 'chat' && stage.value !== 'start')
const showBack = computed(() => view.value === 'chat')
const subtitle = computed(() =>
  view.value === 'list' && history.value.length ? `${history.value.length} letter${history.value.length === 1 ? '' : 's'}` : 'explains official letters'
)

function openCamera() { cameraInput.value?.click() }
function openUpload() { uploadInput.value?.click() }

function onFile(e) {
  const file = e.target.files?.[0]
  e.target.value = '' // allow picking the same file again
  if (!file) return
  if (view.value === 'list' || stage.value === 'review' || stage.value === 'answered') reset()
  startWithFile(file)
}
</script>

<template>
  <div class="app">
    <AppHeader
      v-model:language="language"
      v-model:auto-redact="autoRedact"
      :show-new="showNew"
      :show-back="showBack"
      :subtitle="subtitle"
      @new="reset"
      @back="showList"
    />
    <ChatList v-if="view === 'list'" @new="reset" @camera="openCamera" @upload="openUpload" />
    <template v-else>
      <DeadlineBanner v-if="analysis" :analysis="analysis" @select="thread?.scrollToAnalysis()" />
      <ChatThread ref="thread" @camera="openCamera" @upload="openUpload" />
      <Composer @camera="openCamera" />
    </template>

    <input ref="cameraInput" class="sr-only" type="file" accept="image/*" capture="environment" tabindex="-1" aria-hidden="true" @change="onFile" />
    <input ref="uploadInput" class="sr-only" type="file" accept="image/*,application/pdf" tabindex="-1" aria-hidden="true" @change="onFile" />
  </div>
</template>
