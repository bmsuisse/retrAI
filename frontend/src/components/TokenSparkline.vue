<script setup lang="ts">
import { computed } from 'vue'
import { useEventStore } from '@/stores/eventStore'
import { useRunStore } from '@/stores/runStore'

const eventStore = useEventStore()
const runStore = useRunStore()

interface TokenDataPoint {
  iteration: number
  prompt: number
  completion: number
  total: number
}

const dataPoints = computed<TokenDataPoint[]>(() => {
  const runId = runStore.activeRun?.runId
  const usage = eventStore.llmUsageEvents
    .filter((e) => !runId || e.run_id === runId)
  const byIter = new Map<number, TokenDataPoint>()
  for (const e of usage) {
    const iter = e.iteration
    if (!byIter.has(iter)) {
      byIter.set(iter, { iteration: iter, prompt: 0, completion: 0, total: 0 })
    }
    const d = byIter.get(iter)!
    d.prompt += (e.payload.prompt_tokens as number) || 0
    d.completion += (e.payload.completion_tokens as number) || 0
    d.total += (e.payload.total_tokens as number) || 0
  }
  return [...byIter.values()].sort((a, b) => a.iteration - b.iteration)
})

const maxTotal = computed(() => {
  if (dataPoints.value.length === 0) return 1
  return Math.max(...dataPoints.value.map((d) => d.total))
})

const svgWidth = 240
const svgHeight = 60
const padding = 4

function barX(index: number): number {
  const count = dataPoints.value.length || 1
  const barWidth = (svgWidth - padding * 2) / count
  return padding + index * barWidth
}

function barWidth(): number {
  const count = dataPoints.value.length || 1
  const w = (svgWidth - padding * 2) / count
  return Math.max(w - 2, 2)
}

function barHeight(value: number): number {
  const h = (value / maxTotal.value) * (svgHeight - padding * 2)
  return Math.max(h, 1)
}

const totalTokens = computed(() =>
  dataPoints.value.reduce((sum, d) => sum + d.total, 0),
)

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}
</script>

<template>
  <div class="sparkline-card">
    <div class="sparkline-header">
      <span class="sparkline-label">Tokens</span>
      <span class="sparkline-total">{{ formatTokens(totalTokens) }}</span>
    </div>
    <svg
      :width="svgWidth"
      :height="svgHeight"
      class="sparkline-svg"
      v-if="dataPoints.length > 0"
    >
      <g v-for="(d, i) in dataPoints" :key="d.iteration">
        <rect
          :x="barX(i)"
          :y="svgHeight - padding - barHeight(d.prompt)"
          :width="barWidth()"
          :height="barHeight(d.prompt)"
          fill="rgba(124, 58, 237, 0.6)"
          rx="1"
        >
          <title>Iter {{ d.iteration }}: {{ d.prompt }} prompt</title>
        </rect>
        <rect
          :x="barX(i)"
          :y="svgHeight - padding - barHeight(d.total)"
          :width="barWidth()"
          :height="barHeight(d.completion)"
          fill="rgba(167, 139, 250, 0.8)"
          rx="1"
        >
          <title>Iter {{ d.iteration }}: {{ d.completion }} completion</title>
        </rect>
      </g>
    </svg>
    <div v-else class="sparkline-empty">—</div>
  </div>
</template>

<style scoped>
.sparkline-card {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 0.75rem 1rem;
  backdrop-filter: blur(12px);
}

.sparkline-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.4rem;
}

.sparkline-label {
  font-size: 0.72rem;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.sparkline-total {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-accent-light);
  font-family: 'JetBrains Mono', monospace;
}

.sparkline-svg {
  width: 100%;
  height: auto;
}

.sparkline-empty {
  color: var(--color-text-muted);
  font-size: 0.85rem;
  text-align: center;
  padding: 0.5rem;
}
</style>
