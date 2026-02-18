<script setup lang="ts">
import { ref } from 'vue'
import type { AgentEvent } from '@/stores/eventStore'

const props = defineProps<{
  event: AgentEvent | null
}>()

const isOpen = ref(false)
const copied = ref(false)

function open() {
  isOpen.value = true
}

function close() {
  isOpen.value = false
}

async function copyContent() {
  if (!props.event) return
  const text = JSON.stringify(props.event.payload, null, 2)
  await navigator.clipboard.writeText(text)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

defineExpose({ open, close })
</script>

<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div v-if="isOpen" class="drawer-backdrop" @click.self="close">
        <div class="drawer">
          <div class="drawer-header">
            <h3 class="drawer-title">
              {{ event?.kind === 'tool_call' ? '⚡' : '✓' }}
              {{ event?.kind === 'tool_call' ? 'Tool Call' : 'Tool Result' }}
            </h3>
            <div class="drawer-actions">
              <button class="btn-icon" @click="copyContent" :title="copied ? 'Copied!' : 'Copy'">
                {{ copied ? '✓' : '📋' }}
              </button>
              <button class="btn-icon btn-close" @click="close">✕</button>
            </div>
          </div>

          <div v-if="event" class="drawer-body">
            <div class="detail-section">
              <span class="detail-label">Tool</span>
              <span class="detail-value tool-name">{{ event.payload.tool }}</span>
            </div>
            <div class="detail-section">
              <span class="detail-label">Iteration</span>
              <span class="detail-value">{{ event.iteration }}</span>
            </div>

            <div v-if="event.kind === 'tool_call'" class="detail-section">
              <span class="detail-label">Arguments</span>
              <pre class="code-block">{{ JSON.stringify(event.payload.args, null, 2) }}</pre>
            </div>

            <div v-if="event.kind === 'tool_result'" class="detail-section">
              <span class="detail-label">Output</span>
              <pre class="code-block result-block">{{ event.payload.content }}</pre>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.drawer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(5, 11, 31, 0.6);
  backdrop-filter: blur(4px);
  z-index: 900;
  display: flex;
  justify-content: flex-end;
}

.drawer {
  width: min(520px, 90vw);
  height: 100vh;
  background: linear-gradient(180deg, #1a0533 0%, #0f0a2e 100%);
  border-left: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  box-shadow: -8px 0 40px rgba(0, 0, 0, 0.4);
}

.drawer-enter-active,
.drawer-leave-active {
  transition: transform 0.3s ease;
}
.drawer-enter-from,
.drawer-leave-to {
  transform: translateX(100%);
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--color-border);
}

.drawer-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-accent-light);
}

.drawer-actions {
  display: flex;
  gap: 0.5rem;
}

.btn-icon {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  color: var(--color-text-muted);
  padding: 0.3rem 0.5rem;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.15s;
}
.btn-icon:hover {
  background: rgba(255, 255, 255, 0.12);
}

.btn-close {
  font-size: 1rem;
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem 1.5rem;
}

.detail-section {
  margin-bottom: 1.25rem;
}

.detail-label {
  display: block;
  font-size: 0.75rem;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.07em;
  margin-bottom: 0.35rem;
}

.detail-value {
  font-size: 0.9rem;
  color: var(--color-text);
}

.tool-name {
  font-weight: 700;
  color: #38bdf8;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.code-block {
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  padding: 1rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.8rem;
  color: var(--color-text);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  max-height: 60vh;
  overflow-y: auto;
  margin: 0;
}

.result-block {
  border-color: rgba(74, 222, 128, 0.15);
}
</style>
