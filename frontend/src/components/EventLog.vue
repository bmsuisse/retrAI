<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { useEventStore, type AgentEvent } from '@/stores/eventStore'
import { useRunStore } from '@/stores/runStore'

const eventStore = useEventStore()
const runStore = useRunStore()
const logEl = ref<HTMLElement | null>(null)
const autoScroll = ref(true)
const searchText = ref('')
const activeFilters = ref<Set<string>>(new Set())

const emit = defineEmits<{
  (e: 'openDrawer', event: AgentEvent): void
}>()

const events = computed(() => {
  const runId = runStore.activeRun?.runId
  let list = eventStore.selectedIteration !== null
    ? eventStore.filteredEvents
    : eventStore.events
  if (runId) {
    list = list.filter((e) => e.run_id === runId)
  }
  if (activeFilters.value.size > 0) {
    list = list.filter((e) => activeFilters.value.has(e.kind))
  }
  if (searchText.value.trim()) {
    const q = searchText.value.toLowerCase()
    list = list.filter((e) => {
      const payload = JSON.stringify(e.payload).toLowerCase()
      return e.kind.includes(q) || payload.includes(q)
    })
  }
  return list
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

const filterKinds = [
  'step_start', 'tool_call', 'tool_result', 'goal_check',
  'reasoning', 'llm_usage', 'error',
]

function toggleFilter(kind: string) {
  const next = new Set(activeFilters.value)
  if (next.has(kind)) next.delete(kind)
  else next.add(kind)
  activeFilters.value = next
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
    reasoning: '#818cf8',
    step_progress: '#2dd4bf',
  }[kind] ?? '#94a3b8'
}

function kindIcon(kind: string): string {
  return {
    step_start: '▸',
    tool_call: '⚡',
    tool_result: '✓',
    goal_check: '🎯',
    human_check_required: '👤',
    human_check_response: '👤',
    iteration_complete: '↻',
    run_end: '■',
    error: '✗',
    log: '·',
    llm_usage: '📊',
    reasoning: '🧠',
    step_progress: '◎',
  }[kind] ?? '·'
}

function formatPayload(kind: string, payload: Record<string, unknown>): string {
  if (kind === 'tool_call') return `${payload.tool}(${JSON.stringify(payload.args).slice(0, 100)})`
  if (kind === 'tool_result') return `${payload.tool}: ${String(payload.content).slice(0, 140)}`
  if (kind === 'goal_check') return `${payload.achieved ? '✓ Achieved' : '… Not yet'} — ${payload.reason}`
  if (kind === 'step_start') return `→ ${payload.node}`
  if (kind === 'run_end') return `${payload.status} — ${payload.reason}`
  if (kind === 'error') return `${payload.error}`
  if (kind === 'reasoning') return String(payload.text).slice(0, 150)
  if (kind === 'llm_usage') return `${payload.model}: ${payload.prompt_tokens}→${payload.completion_tokens} (${payload.total_tokens} total)`
  return JSON.stringify(payload).slice(0, 140)
}

function timeAgo(ts: number): string {
  const diff = Math.floor(Date.now() / 1000 - ts)
  if (diff < 2) return 'now'
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return new Date(ts * 1000).toLocaleTimeString()
}

function isClickable(kind: string): boolean {
  return kind === 'tool_call' || kind === 'tool_result'
}

function onClickEntry(event: AgentEvent) {
  if (isClickable(event.kind)) {
    emit('openDrawer', event)
  }
}
</script>

<template>
  <div class="event-log">
    <div class="log-header">
      <h2 class="section-title">📡 Event Log</h2>
      <span class="count">{{ events.length }} events</span>
    </div>

    <div class="filter-bar">
      <input
        v-model="searchText"
        class="search-input"
        placeholder="Search events…"
      />
      <div class="filter-chips">
        <button
          v-for="kind in filterKinds"
          :key="kind"
          class="filter-chip"
          :class="{ active: activeFilters.has(kind) }"
          :style="activeFilters.has(kind) ? { borderColor: kindColor(kind), color: kindColor(kind) } : {}"
          @click="toggleFilter(kind)"
        >
          {{ kind.replace('_', ' ') }}
        </button>
      </div>
    </div>

    <div ref="logEl" class="log-body" @scroll="onScroll">
      <div v-if="events.length === 0" class="empty">
        <span>No events yet. Start a run to see live output.</span>
      </div>

      <div
        v-for="event in events"
        :key="event.id"
        class="log-entry"
        :class="[event.kind, { clickable: isClickable(event.kind) }]"
        @click="onClickEntry(event)"
      >
        <span class="log-icon" :style="{ color: kindColor(event.kind) }">
          {{ kindIcon(event.kind) }}
        </span>
        <span class="log-time" :title="new Date(event.ts * 1000).toLocaleString()">
          {{ timeAgo(event.ts) }}
        </span>
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
  padding: 1rem 1.25rem 0.5rem;
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

.filter-bar {
  padding: 0 1.25rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  border-bottom: 1px solid var(--color-border);
}

.search-input {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 0.4rem 0.75rem;
  color: var(--color-text);
  font-size: 0.82rem;
  outline: none;
  transition: border-color 0.2s;
}
.search-input:focus {
  border-color: var(--color-accent);
}
.search-input::placeholder {
  color: #475569;
}

.filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.filter-chip {
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  padding: 0.15rem 0.5rem;
  font-size: 0.68rem;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: all 0.15s;
}
.filter-chip:hover {
  background: rgba(255, 255, 255, 0.04);
}
.filter-chip.active {
  background: rgba(124, 58, 237, 0.1);
}

.log-body {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem 0;
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
  gap: 0.4rem;
  padding: 0.25rem 1.25rem;
  font-size: 0.8rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  transition: background 0.12s;
}
.log-entry:hover {
  background: rgba(255, 255, 255, 0.03);
}
.log-entry.clickable {
  cursor: pointer;
}
.log-entry.clickable:hover {
  background: rgba(124, 58, 237, 0.08);
}

.log-icon {
  flex-shrink: 0;
  font-size: 0.75rem;
  min-width: 1.2rem;
  text-align: center;
}

.log-time {
  color: #475569;
  flex-shrink: 0;
  font-size: 0.7rem;
  min-width: 3.5rem;
}

.log-iter {
  color: #374151;
  flex-shrink: 0;
  font-size: 0.7rem;
  min-width: 1.5rem;
}

.log-kind {
  flex-shrink: 0;
  min-width: 8.5rem;
  font-weight: 600;
  font-size: 0.72rem;
}

.log-content {
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.78rem;
}
</style>
