<script setup lang="ts">
import { onMounted } from 'vue'
import { useRunStore, type RunStatus } from '@/stores/runStore'

const runStore = useRunStore()

onMounted(() => {
  runStore.fetchHistory()
})

function statusColor(status: RunStatus): string {
  return {
    idle: '#64748b',
    running: '#a78bfa',
    achieved: '#4ade80',
    failed: '#f87171',
    aborted: '#fbbf24',
  }[status]
}

function statusIcon(status: RunStatus): string {
  return {
    idle: '○',
    running: '◉',
    achieved: '✓',
    failed: '✗',
    aborted: '⏹',
  }[status]
}
</script>

<template>
  <div class="history-panel">
    <h2 class="section-title">📋 Run History</h2>

    <div v-if="runStore.allRuns.length === 0" class="empty-state">
      <p>No runs yet.</p>
    </div>

    <div class="history-list">
      <div
        v-for="run in runStore.allRuns"
        :key="run.runId"
        class="history-item"
        :class="{ active: run.runId === runStore.activeRun?.runId }"
      >
        <div class="item-header">
          <span class="status-badge" :style="{ color: statusColor(run.status) }">
            {{ statusIcon(run.status) }} {{ run.status.toUpperCase() }}
          </span>
          <span class="goal-label">{{ run.goal }}</span>
        </div>
        <div class="item-meta">
          <span class="meta-chip">{{ run.modelName }}</span>
          <span class="meta-chip">{{ run.iteration }}/{{ run.maxIterations }} iter</span>
        </div>
        <div v-if="run.goalReason" class="item-reason">
          {{ run.goalReason }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-panel {
  padding: 1.5rem;
}

.section-title {
  margin: 0 0 1rem;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-accent-light);
}

.empty-state {
  color: var(--color-text-muted);
  font-size: 0.9rem;
  text-align: center;
  padding: 2rem;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.history-item {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 0.85rem 1rem;
  transition: background 0.2s;
  cursor: default;
}
.history-item:hover {
  background: rgba(255, 255, 255, 0.06);
}
.history-item.active {
  border-color: var(--color-accent);
  background: rgba(124, 58, 237, 0.08);
}

.item-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}

.status-badge {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.1em;
}

.goal-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-text);
}

.item-meta {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.meta-chip {
  font-size: 0.7rem;
  color: var(--color-text-muted);
  background: rgba(255, 255, 255, 0.04);
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
}

.item-reason {
  margin-top: 0.35rem;
  font-size: 0.78rem;
  color: var(--color-text-muted);
  font-style: italic;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
