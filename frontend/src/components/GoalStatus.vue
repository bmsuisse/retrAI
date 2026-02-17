<script setup lang="ts">
import { computed } from 'vue'
import { useRunStore } from '@/stores/runStore'
import { useEventStore } from '@/stores/eventStore'

const runStore = useRunStore()
const eventStore = useEventStore()

const run = computed(() => runStore.activeRun)

const statusConfig = computed(() => {
  const status = run.value?.status ?? 'idle'
  return {
    idle: { label: 'IDLE', color: '#64748b', glow: 'none' },
    running: { label: 'RUNNING', color: '#a78bfa', glow: '0 0 12px #7c3aed88' },
    achieved: { label: 'ACHIEVED', color: '#4ade80', glow: '0 0 12px #22c55e88' },
    failed: { label: 'FAILED', color: '#f87171', glow: '0 0 12px #ef444488' },
    aborted: { label: 'ABORTED', color: '#fbbf24', glow: '0 0 12px #f59e0b88' },
  }[status]
})

const progress = computed(() => {
  if (!run.value) return 0
  return Math.round((run.value.iteration / run.value.maxIterations) * 100)
})

const totalTokens = computed(() => {
  if (!run.value) return 0
  return eventStore.events
    .filter((e) => e.run_id === run.value!.runId && e.kind === 'llm_usage')
    .reduce((sum, e) => sum + ((e.payload.total_tokens as number) || 0), 0)
})

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}
</script>

<template>
  <div class="goal-status">
    <div class="status-row">
      <div class="badge" :style="{ color: statusConfig?.color, boxShadow: statusConfig?.glow }">
        <span class="dot" :class="{ pulse: run?.status === 'running' }" />
        {{ statusConfig?.label }}
      </div>
      <span v-if="run" class="iter-label">
        {{ run.iteration }} / {{ run.maxIterations }} iterations
      </span>
    </div>

    <div v-if="run" class="progress-bar">
      <div class="progress-fill" :style="{ width: progress + '%' }" />
    </div>

    <div v-if="run" class="meta">
      <span class="meta-item">
        <span class="meta-key">Goal</span>
        <span class="meta-val">{{ run.goal }}</span>
      </span>
      <span class="meta-item">
        <span class="meta-key">Model</span>
        <span class="meta-val">{{ run.modelName }}</span>
      </span>
      <span class="meta-item">
        <span class="meta-key">CWD</span>
        <span class="meta-val truncate">{{ run.cwd }}</span>
      </span>
      <span v-if="totalTokens > 0" class="meta-item">
        <span class="meta-key">Tokens</span>
        <span class="meta-val">{{ formatTokens(totalTokens) }}</span>
      </span>
    </div>

    <p v-if="run?.goalReason" class="reason">{{ run.goalReason }}</p>
  </div>
</template>

<style scoped>
.goal-status {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  backdrop-filter: blur(12px);
}

.status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.badge {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  border: 1px solid currentColor;
  border-radius: 999px;
  padding: 0.25rem 0.75rem;
  transition: box-shadow 0.3s;
}

.dot {
  width: 8px;
  height: 8px;
  background: currentColor;
  border-radius: 50%;
}
.dot.pulse {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.75); }
}

.iter-label {
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

.progress-bar {
  height: 4px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 1rem;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #7c3aed, #a78bfa);
  border-radius: 2px;
  transition: width 0.5s ease;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
}

.meta-key {
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.meta-val {
  color: var(--color-text);
  font-family: 'JetBrains Mono', monospace;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reason {
  font-size: 0.85rem;
  color: var(--color-text-muted);
  margin: 0.5rem 0 0;
  font-style: italic;
}
</style>
