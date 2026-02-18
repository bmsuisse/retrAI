<script setup lang="ts">
import { computed } from 'vue'
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { MiniMap } from '@vue-flow/minimap'
import { useEventStore } from '@/stores/eventStore'
import { useRunStore } from '@/stores/runStore'
import type { Node, Edge } from '@vue-flow/core'

const eventStore = useEventStore()
const runStore = useRunStore()

const activeNode = computed(() => {
  const run = runStore.activeRun
  if (!run) return null
  const stepEvents = eventStore.events
    .filter((e) => e.run_id === run.runId && e.kind === 'step_start')
  if (stepEvents.length === 0) return null
  return stepEvents[stepEvents.length - 1].payload.node as string
})

const toolCallCount = computed(() => {
  const run = runStore.activeRun
  if (!run) return 0
  return eventStore.toolCallEvents.filter((e) => e.run_id === run.runId).length
})

const nodeStyle = (id: string) => {
  const isActive = activeNode.value === id
  const isEnd = id === 'end'
  const isStart = id === 'start'
  return {
    background: isEnd
      ? 'rgba(100,116,139,0.15)'
      : isStart
        ? 'rgba(124,58,237,0.15)'
        : isActive
          ? 'rgba(124,58,237,0.35)'
          : 'rgba(15,10,46,0.85)',
    border: `2px solid ${isActive ? '#a78bfa' : isEnd ? '#475569' : isStart ? 'rgba(124,58,237,0.5)' : 'rgba(124,58,237,0.25)'}`,
    color: '#e2e8f0',
    borderRadius: '14px',
    padding: '12px 20px',
    fontFamily: "'Inter', system-ui, sans-serif",
    fontSize: '13px',
    fontWeight: isActive ? '700' : '500',
    boxShadow: isActive
      ? '0 0 24px rgba(124,58,237,0.5), inset 0 0 12px rgba(124,58,237,0.15)'
      : '0 2px 8px rgba(0,0,0,0.2)',
    transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
    backdropFilter: 'blur(8px)',
  }
}

const nodeLabel = (id: string) => {
  const run = runStore.activeRun
  const labels: Record<string, string> = {
    start: '▶ START',
    plan: `🧠 plan`,
    act: `⚡ act — ${toolCallCount.value} calls`,
    evaluate: '🔍 evaluate',
    human_check: '👤 human check',
    end: '■ END',
  }
  if (id === 'plan' && run) {
    return `🧠 plan — iter ${run.iteration}`
  }
  return labels[id] || id
}

const nodes = computed<Node[]>(() => [
  { id: 'start', type: 'input', position: { x: 250, y: 10 }, label: nodeLabel('start'), style: nodeStyle('start') },
  { id: 'plan', position: { x: 210, y: 110 }, label: nodeLabel('plan'), style: nodeStyle('plan') },
  { id: 'act', position: { x: 400, y: 210 }, label: nodeLabel('act'), style: nodeStyle('act') },
  { id: 'evaluate', position: { x: 210, y: 310 }, label: nodeLabel('evaluate'), style: nodeStyle('evaluate') },
  { id: 'human_check', position: { x: 30, y: 400 }, label: nodeLabel('human_check'), style: nodeStyle('human_check') },
  { id: 'end', type: 'output', position: { x: 250, y: 500 }, label: nodeLabel('end'), style: nodeStyle('end') },
])

const edges = computed<Edge[]>(() => [
  { id: 'e-start-plan', source: 'start', target: 'plan', animated: activeNode.value === 'plan', style: edgeStyle('plan') },
  { id: 'e-plan-act', source: 'plan', target: 'act', label: 'has tools', animated: activeNode.value === 'act', style: edgeStyle('act') },
  { id: 'e-plan-eval', source: 'plan', target: 'evaluate', label: 'no tools', animated: false },
  { id: 'e-act-eval', source: 'act', target: 'evaluate', animated: activeNode.value === 'evaluate', style: edgeStyle('evaluate') },
  { id: 'e-eval-plan', source: 'evaluate', target: 'plan', label: 'continue', animated: activeNode.value === 'plan', style: edgeStyle('plan') },
  { id: 'e-eval-hitl', source: 'evaluate', target: 'human_check', label: 'hitl', animated: activeNode.value === 'human_check' },
  { id: 'e-eval-end', source: 'evaluate', target: 'end', label: 'done' },
  { id: 'e-hitl-plan', source: 'human_check', target: 'plan', label: 'approve' },
  { id: 'e-hitl-end', source: 'human_check', target: 'end', label: 'abort' },
])

function edgeStyle(targetNode: string) {
  const isActive = activeNode.value === targetNode
  return {
    stroke: isActive ? '#a78bfa' : 'rgba(124, 58, 237, 0.35)',
    strokeWidth: isActive ? 3 : 2,
  }
}
</script>

<template>
  <div class="agent-graph">
    <VueFlow
      :nodes="nodes"
      :edges="edges"
      :edges-updatable="false"
      :nodes-draggable="false"
      :nodes-connectable="false"
      :zoom-on-scroll="false"
      :pan-on-drag="false"
      fit-view-on-init
      class="flow"
    >
      <Background pattern-color="rgba(124,58,237,0.06)" :gap="24" />
      <MiniMap
        :node-color="() => 'rgba(124,58,237,0.5)'"
        mask-color="rgba(5,11,31,0.8)"
        class="minimap"
      />
    </VueFlow>
  </div>
</template>

<style scoped>
.agent-graph {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  overflow: hidden;
  backdrop-filter: blur(12px);
  height: 100%;
  position: relative;
}

.flow {
  width: 100%;
  height: 100%;
}

:deep(.vue-flow__edge-path) {
  stroke: rgba(124, 58, 237, 0.35);
  stroke-width: 2;
  transition: stroke 0.3s, stroke-width 0.3s;
}

:deep(.vue-flow__edge.animated .vue-flow__edge-path) {
  stroke: #a78bfa;
  stroke-width: 3;
  filter: drop-shadow(0 0 4px rgba(167, 139, 250, 0.5));
}

:deep(.vue-flow__edge-label) {
  font-size: 10px;
  fill: #64748b;
  background: transparent;
}

.minimap {
  position: absolute;
  bottom: 8px;
  right: 8px;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  overflow: hidden;
}

:deep(.vue-flow__minimap) {
  background: rgba(15, 10, 46, 0.9) !important;
}
</style>
