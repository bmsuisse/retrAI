<script setup lang="ts">
import { computed } from 'vue'
import { useEventStore } from '@/stores/eventStore'
import { useRunStore } from '@/stores/runStore'

const eventStore = useEventStore()
const runStore = useRunStore()

interface IterNode {
  iteration: number
  toolCalls: number
  goalResult: boolean | null
  isActive: boolean
}

const iterations = computed<IterNode[]>(() => {
  const runId = runStore.activeRun?.runId
  const groups = eventStore.iterationGroups
  const currentIter = runStore.activeRun?.iteration ?? 0
  const nodes: IterNode[] = []

  for (const [iter, events] of groups) {
    if (runId && events.some((e) => e.run_id !== runId)) continue
    const toolCalls = events.filter((e) => e.kind === 'tool_call').length
    const goalChecks = events.filter((e) => e.kind === 'goal_check')
    const goalResult = goalChecks.length > 0
      ? (goalChecks[goalChecks.length - 1].payload.achieved as boolean)
      : null
    nodes.push({
      iteration: iter,
      toolCalls,
      goalResult,
      isActive: iter === currentIter && runStore.isRunning,
    })
  }
  return nodes.sort((a, b) => a.iteration - b.iteration)
})

function selectIteration(iter: number) {
  if (eventStore.selectedIteration === iter) {
    eventStore.setSelectedIteration(null)
  } else {
    eventStore.setSelectedIteration(iter)
  }
}
</script>

<template>
  <div class="timeline-bar">
    <span class="timeline-label">Iterations</span>
    <div class="timeline-scroll">
      <div
        v-for="node in iterations"
        :key="node.iteration"
        class="timeline-node"
        :class="{
          active: node.isActive,
          achieved: node.goalResult === true,
          selected: eventStore.selectedIteration === node.iteration,
        }"
        @click="selectIteration(node.iteration)"
      >
        <span class="node-number">{{ node.iteration }}</span>
        <span v-if="node.toolCalls > 0" class="node-tools">
          {{ node.toolCalls }} <span class="tools-icon">⚡</span>
        </span>
        <span v-if="node.goalResult === true" class="node-check">✓</span>
        <span v-if="node.goalResult === false" class="node-x">…</span>
      </div>
      <div v-if="iterations.length === 0" class="timeline-empty">
        No iterations yet
      </div>
    </div>
    <button
      v-if="eventStore.selectedIteration !== null"
      class="clear-filter"
      @click="eventStore.setSelectedIteration(null)"
    >
      Clear filter
    </button>
  </div>
</template>

<style scoped>
.timeline-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 0.5rem 1rem;
  backdrop-filter: blur(12px);
}

.timeline-label {
  font-size: 0.72rem;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  flex-shrink: 0;
}

.timeline-scroll {
  display: flex;
  gap: 0.4rem;
  overflow-x: auto;
  flex: 1;
  padding: 0.25rem 0;
  scrollbar-width: thin;
}

.timeline-node {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.3rem 0.6rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  font-size: 0.75rem;
  color: var(--color-text-muted);
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.2s;
}

.timeline-node:hover {
  background: rgba(124, 58, 237, 0.1);
  border-color: rgba(124, 58, 237, 0.3);
}

.timeline-node.selected {
  background: rgba(124, 58, 237, 0.2);
  border-color: var(--color-accent);
  color: var(--color-text);
}

.timeline-node.active {
  border-color: var(--color-accent-light);
  box-shadow: 0 0 10px rgba(124, 58, 237, 0.4);
  animation: pulse-glow 2s ease-in-out infinite;
}

.timeline-node.achieved {
  border-color: rgba(74, 222, 128, 0.4);
}

@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 8px rgba(124, 58, 237, 0.3); }
  50% { box-shadow: 0 0 16px rgba(124, 58, 237, 0.6); }
}

.node-number {
  font-weight: 700;
  color: var(--color-text);
}

.node-tools {
  font-size: 0.7rem;
  color: #38bdf8;
}

.tools-icon {
  font-size: 0.65rem;
}

.node-check {
  color: #4ade80;
  font-weight: 700;
}

.node-x {
  color: #fbbf24;
}

.timeline-empty {
  color: var(--color-text-muted);
  font-size: 0.8rem;
  padding: 0.25rem;
}

.clear-filter {
  background: none;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  color: var(--color-text-muted);
  font-size: 0.72rem;
  padding: 0.25rem 0.5rem;
  cursor: pointer;
  flex-shrink: 0;
  transition: color 0.2s;
}
.clear-filter:hover {
  color: var(--color-text);
}
</style>
