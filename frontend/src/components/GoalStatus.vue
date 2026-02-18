<script setup lang="ts">
import { computed } from 'vue'
import { useRunStore } from '@/stores/runStore'
import { useEventStore } from '@/stores/eventStore'

const runStore = useRunStore()
const eventStore = useEventStore()

const run = computed(() => runStore.activeRun)
const isRunning = computed(() => runStore.isRunning)

function statusLabel(s: string | undefined): string {
  return {
    idle: '○ IDLE',
    running: '◉ RUNNING',
    achieved: '✓ ACHIEVED',
    failed: '✗ FAILED',
    aborted: '⏹ ABORTED',
  }[s ?? 'idle'] ?? '○ IDLE'
}

function statusColor(s: string | undefined): string {
  return {
    idle: '#64748b',
    running: '#a78bfa',
    achieved: '#4ade80',
    failed: '#f87171',
    aborted: '#fbbf24',
  }[s ?? 'idle'] ?? '#64748b'
}

const progressAngle = computed(() => {
  if (!run.value) return 0
  const pct = run.value.maxIterations > 0
    ? run.value.iteration / run.value.maxIterations
    : 0
  return Math.min(pct, 1) * 360
})

const totalTokens = computed(() => {
  const runId = run.value?.runId
  if (!runId) return 0
  let total = 0
  for (const e of eventStore.llmUsageEvents) {
    if (e.run_id === runId) {
      total += (e.payload.total_tokens as number) || 0
    }
  }
  return total
})

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}
</script>

<template>
  <div class="goal-status">
    <!-- Progress ring -->
    <div class="ring-wrap">
      <svg width="72" height="72" viewBox="0 0 72 72">
        <circle
          cx="36" cy="36" r="30"
          fill="none"
          stroke="rgba(124,58,237,0.12)"
          stroke-width="5"
        />
        <circle
          cx="36" cy="36" r="30"
          fill="none"
          :stroke="statusColor(run?.status)"
          stroke-width="5"
          stroke-linecap="round"
          :stroke-dasharray="`${progressAngle * Math.PI * 30 / 180} 999`"
          transform="rotate(-90 36 36)"
          style="transition: stroke-dasharray 0.6s cubic-bezier(0.4, 0, 0.2, 1)"
        />
      </svg>
      <div class="ring-center">
        <template v-if="run">
          <span class="ring-big">{{ run.iteration }}</span>
          <span class="ring-small">/{{ run.maxIterations }}</span>
        </template>
        <span v-else class="ring-big">—</span>
      </div>
    </div>

    <!-- Status + Details -->
    <div class="status-details">
      <div class="status-row">
        <span class="status-badge" :style="{ color: statusColor(run?.status) }">
          {{ statusLabel(run?.status) }}
        </span>
        <span v-if="isRunning" class="elapsed">{{ runStore.elapsedFormatted }}</span>
      </div>
      <div v-if="run" class="detail-grid">
        <div class="detail-cell">
          <span class="label">Goal</span>
          <span class="value goal-val">{{ run.goal }}</span>
        </div>
        <div class="detail-cell">
          <span class="label">Model</span>
          <span class="value">{{ run.modelName }}</span>
        </div>
        <div class="detail-cell">
          <span class="label">CWD</span>
          <span class="value mono">{{ run.cwd }}</span>
        </div>
        <div class="detail-cell">
          <span class="label">Tokens</span>
          <span class="value mono">{{ formatTokens(totalTokens) }}</span>
        </div>
      </div>
      <div v-if="run?.goalReason" class="reason">
        {{ run.goalReason }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.goal-status {
  display: flex;
  align-items: flex-start;
  gap: 1.25rem;
  padding: 1.25rem;
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  backdrop-filter: blur(12px);
}

.ring-wrap {
  position: relative;
  width: 72px;
  height: 72px;
  flex-shrink: 0;
}

.ring-wrap svg {
  display: block;
}

.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ring-big {
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--color-text);
  font-family: 'JetBrains Mono', monospace;
}

.ring-small {
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

.status-details {
  flex: 1;
  min-width: 0;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.6rem;
}

.status-badge {
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.1em;
}

.elapsed {
  font-size: 0.78rem;
  color: var(--color-text-muted);
  font-family: 'JetBrains Mono', monospace;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.4rem 1rem;
}

.detail-cell {
  display: flex;
  flex-direction: column;
}

.label {
  font-size: 0.65rem;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.value {
  font-size: 0.82rem;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.goal-val {
  font-weight: 600;
  color: var(--color-accent-light);
}

.mono {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem;
}

.reason {
  margin-top: 0.5rem;
  font-size: 0.8rem;
  color: var(--color-text-muted);
  font-style: italic;
  border-top: 1px solid var(--color-border);
  padding-top: 0.5rem;
}
</style>
