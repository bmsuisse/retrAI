<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { useEventStore } from '@/stores/eventStore'
import { useRunStore } from '@/stores/runStore'

const eventStore = useEventStore()
const runStore = useRunStore()
const panelEl = ref<HTMLElement | null>(null)
const autoScroll = ref(true)

const reasoningEntries = computed(() => {
  const runId = runStore.activeRun?.runId
  if (!runId) return eventStore.reasoningEvents
  return eventStore.reasoningEvents.filter((e) => e.run_id === runId)
})

const isThinking = computed(() => {
  if (!runStore.isRunning) return false
  const runId = runStore.activeRun?.runId
  if (!runId) return false
  const stepStarts = eventStore.events.filter(
    (e) => e.run_id === runId && e.kind === 'step_start',
  )
  if (stepStarts.length === 0) return false
  const lastStep = stepStarts[stepStarts.length - 1]
  if (lastStep.payload.node !== 'plan') return false
  const laterReasoning = reasoningEntries.value.find(
    (r) => r.ts > lastStep.ts,
  )
  return !laterReasoning
})

watch(
  () => reasoningEntries.value.length,
  async () => {
    if (autoScroll.value) {
      await nextTick()
      panelEl.value?.scrollTo({ top: panelEl.value.scrollHeight, behavior: 'smooth' })
    }
  },
)
</script>

<template>
  <div class="reasoning-panel">
    <div class="panel-header">
      <h2 class="section-title">
        <span class="title-icon">🧠</span> AI Reasoning
      </h2>
      <span class="entry-count">{{ reasoningEntries.length }} thoughts</span>
    </div>

    <div ref="panelEl" class="panel-body">
      <div v-if="reasoningEntries.length === 0 && !isThinking" class="empty-state">
        <div class="empty-icon">💭</div>
        <p>The AI's reasoning will appear here during a run.</p>
      </div>

      <div v-if="isThinking" class="thinking-indicator">
        <div class="thinking-dots">
          <span class="dot d1" />
          <span class="dot d2" />
          <span class="dot d3" />
        </div>
        <span class="thinking-label">Thinking…</span>
      </div>

      <div
        v-for="entry in reasoningEntries"
        :key="entry.id"
        class="reasoning-entry"
      >
        <div class="entry-header">
          <span class="iter-badge">Iter {{ entry.iteration }}</span>
          <span v-if="entry.payload.has_tool_calls" class="tool-hint">→ tool calls</span>
        </div>
        <div class="entry-text">{{ entry.payload.text }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.reasoning-panel {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  backdrop-filter: blur(12px);
  min-height: 0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem 0.75rem;
  border-bottom: 1px solid var(--color-border);
}

.section-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-accent-light);
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.title-icon {
  font-size: 1.1rem;
}

.entry-count {
  font-size: 0.78rem;
  color: var(--color-text-muted);
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  text-align: center;
}

.empty-icon {
  font-size: 2.5rem;
  margin-bottom: 0.75rem;
  opacity: 0.5;
}

.empty-state p {
  color: var(--color-text-muted);
  font-size: 0.9rem;
  margin: 0;
}

.thinking-indicator {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  margin-bottom: 0.5rem;
  background: rgba(124, 58, 237, 0.1);
  border: 1px solid rgba(124, 58, 237, 0.2);
  border-radius: 10px;
}

.thinking-dots {
  display: flex;
  gap: 4px;
}

.thinking-dots .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-accent-light);
  animation: bounce 1.4s ease-in-out infinite;
}

.dot.d1 { animation-delay: 0s; }
.dot.d2 { animation-delay: 0.2s; }
.dot.d3 { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1.2); }
}

.thinking-label {
  font-size: 0.85rem;
  color: var(--color-accent-light);
  font-style: italic;
}

.reasoning-entry {
  padding: 0.75rem 1rem;
  margin-bottom: 0.5rem;
  background: rgba(255, 255, 255, 0.03);
  border-left: 3px solid var(--color-accent);
  border-radius: 0 8px 8px 0;
  transition: background 0.2s;
}

.reasoning-entry:hover {
  background: rgba(255, 255, 255, 0.06);
}

.entry-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.4rem;
}

.iter-badge {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--color-accent-light);
  background: rgba(124, 58, 237, 0.15);
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  letter-spacing: 0.05em;
}

.tool-hint {
  font-size: 0.72rem;
  color: #38bdf8;
}

.entry-text {
  font-size: 0.85rem;
  color: var(--color-text);
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
