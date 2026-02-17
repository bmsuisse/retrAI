<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { useEventStore } from '@/stores/eventStore'
import { useRunStore } from '@/stores/runStore'

const eventStore = useEventStore()
const runStore = useRunStore()
const logEl = ref<HTMLElement | null>(null)
const autoScroll = ref(true)

const events = computed(() => {
  const runId = runStore.activeRun?.runId
  if (!runId) return eventStore.events
  return eventStore.events.filter((e) => e.run_id === runId)
})

watch(
  () => events.value.length,
  async () => {
    if (autoScroll.value) {
      await nextTick()
      logEl.value?.scrollTo({ top: logEl.value.scrollHeight, behavior: 'smooth' })
    }
  },
)

function onScroll(e: Event) {
  const el = e.target as HTMLElement
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50
  autoScroll.value = atBottom
}

function kindColor(kind: string): string {
  return {
    step_start: '#a78bfa',
    tool_call: '#38bdf8',
    tool_result: '#4ade80',
    goal_check: '#fbbf24',
    human_check_required: '#fb923c',
    human_check_response: '#fb923c',
    iteration_complete: '#64748b',
    run_end: '#e2e8f0',
    error: '#f87171',
    log: '#94a3b8',
    llm_usage: '#c084fc',
  }[kind] ?? '#94a3b8'
}

function formatPayload(kind: string, payload: Record<string, unknown>): string {
  if (kind === 'tool_call') return `${payload.tool}(${JSON.stringify(payload.args).slice(0, 80)})`
  if (kind === 'tool_result') return `${payload.tool}: ${String(payload.content).slice(0, 120)}`
  if (kind === 'goal_check') return `${payload.achieved ? '✓' : '…'} ${payload.reason}`
  if (kind === 'step_start') return `node=${payload.node}`
  if (kind === 'run_end') return `status=${payload.status} — ${payload.reason}`
  if (kind === 'error') return `ERROR: ${payload.error}`
  if (kind === 'llm_usage') return `${payload.model}: ${payload.prompt_tokens}→${payload.completion_tokens} (${payload.total_tokens} total)`
  return JSON.stringify(payload).slice(0, 120)
}

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString()
}
</script>

<template>
  <div class="event-log">
    <div class="log-header">
      <h2 class="section-title">Event Log</h2>
      <span class="count">{{ events.length }} events</span>
    </div>

    <div ref="logEl" class="log-body" @scroll="onScroll">
      <div v-if="events.length === 0" class="empty">
        <span>No events yet. Start a run to see live output.</span>
      </div>

      <div
        v-for="event in events"
        :key="event.id"
        class="log-entry"
        :class="event.kind"
      >
        <span class="log-time">{{ formatTime(event.ts) }}</span>
        <span class="log-iter">[{{ event.iteration }}]</span>
        <span class="log-kind" :style="{ color: kindColor(event.kind) }">
          {{ event.kind }}
        </span>
        <span class="log-content">{{ formatPayload(event.kind, event.payload) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.event-log {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  backdrop-filter: blur(12px);
  min-height: 0;
}

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem 0.75rem;
  border-bottom: 1px solid var(--color-border);
}

.section-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-accent-light);
}

.count {
  font-size: 0.78rem;
  color: var(--color-text-muted);
}

.log-body {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem 0;
}

.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  color: var(--color-text-muted);
  font-size: 0.9rem;
}

.log-entry {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  padding: 0.3rem 1.25rem;
  font-size: 0.82rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  transition: background 0.15s;
}
.log-entry:hover {
  background: rgba(255, 255, 255, 0.04);
}

.log-time {
  color: var(--color-text-muted);
  flex-shrink: 0;
  font-size: 0.75rem;
}

.log-iter {
  color: #475569;
  flex-shrink: 0;
  font-size: 0.75rem;
  min-width: 2rem;
}

.log-kind {
  flex-shrink: 0;
  min-width: 9rem;
  font-weight: 600;
}

.log-content {
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
