<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRunStore } from '@/stores/runStore'
import { useEventStore } from '@/stores/eventStore'
import RunControls from '@/components/RunControls.vue'
import GoalStatus from '@/components/GoalStatus.vue'
import AgentGraph from '@/components/AgentGraph.vue'
import EventLog from '@/components/EventLog.vue'
import ReasoningPanel from '@/components/ReasoningPanel.vue'
import TokenSparkline from '@/components/TokenSparkline.vue'
import IterationTimeline from '@/components/IterationTimeline.vue'
import HumanCheckModal from '@/components/HumanCheckModal.vue'
import ToolResultDrawer from '@/components/ToolResultDrawer.vue'
import RunHistoryList from '@/components/RunHistoryList.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import type { AgentEvent } from '@/stores/eventStore'

const runStore = useRunStore()
const eventStore = useEventStore()

const activeTab = ref<'dashboard' | 'history' | 'settings'>('dashboard')
const drawerEvent = ref<AgentEvent | null>(null)
const drawerRef = ref<InstanceType<typeof ToolResultDrawer> | null>(null)

function openDrawer(event: AgentEvent) {
  drawerEvent.value = event
  drawerRef.value?.open()
}

onMounted(() => {
  runStore.fetchHistory()
  document.addEventListener('keydown', handleKeys)
})

function handleKeys(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    drawerRef.value?.close()
  }
  if ((e.metaKey || e.ctrlKey) && e.key === '1') {
    e.preventDefault()
    activeTab.value = 'dashboard'
  }
  if ((e.metaKey || e.ctrlKey) && e.key === '2') {
    e.preventDefault()
    activeTab.value = 'history'
  }
  if ((e.metaKey || e.ctrlKey) && e.key === '3') {
    e.preventDefault()
    activeTab.value = 'settings'
  }
}
</script>

<template>
  <div class="app-shell">
    <!-- Top header / brand bar -->
    <header class="app-header">
      <div class="brand">
        <span class="brand-icon">◆</span>
        <h1 class="brand-name">retr<span class="brand-accent">AI</span></h1>
      </div>
      <nav class="tab-nav">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'dashboard' }"
          @click="activeTab = 'dashboard'"
        >
          Dashboard
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'history' }"
          @click="activeTab = 'history'"
        >
          History
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'settings' }"
          @click="activeTab = 'settings'"
        >
          Settings
        </button>
      </nav>
      <div class="header-right">
        <span v-if="runStore.isRunning" class="live-dot" />
        <span class="kbd-hint">
          <kbd>⌘1</kbd>/<kbd>⌘2</kbd>/<kbd>⌘3</kbd>
        </span>
      </div>
    </header>

    <!-- Tab: Dashboard -->
    <main v-if="activeTab === 'dashboard'" class="dashboard">
      <!-- Left sidebar: controls + status + token chart -->
      <div class="sidebar-col">
        <RunControls />
        <GoalStatus />
        <TokenSparkline />
      </div>

      <!-- Center column: graph + reasoning -->
      <div class="center-col">
        <div class="graph-panel">
          <AgentGraph />
        </div>
        <ReasoningPanel />
      </div>

      <!-- Right column: event log -->
      <div class="log-col">
        <EventLog @open-drawer="openDrawer" />
      </div>

      <!-- Bottom bar: iteration timeline -->
      <div class="bottom-bar">
        <IterationTimeline />
      </div>
    </main>

    <!-- Tab: History -->
    <main v-else-if="activeTab === 'history'" class="tab-content">
      <RunHistoryList />
    </main>

    <!-- Tab: Settings -->
    <main v-else class="tab-content">
      <SettingsPanel />
    </main>

    <!-- Overlays -->
    <HumanCheckModal v-if="runStore.awaitingHuman" />
    <ToolResultDrawer ref="drawerRef" :event="drawerEvent" />
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  min-height: 0;
  background: var(--color-bg);
  color: var(--color-text);
}

/* ── Header ───────────────────────────────────── */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0 1.25rem;
  height: 52px;
  background: rgba(15, 10, 46, 0.9);
  border-bottom: 1px solid var(--color-border);
  backdrop-filter: blur(16px);
  flex-shrink: 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.brand-icon {
  font-size: 1.1rem;
  color: var(--color-accent-light);
}

.brand-name {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.02em;
}

.brand-accent {
  color: var(--color-accent-light);
}

.tab-nav {
  display: flex;
  gap: 0.25rem;
}

.tab-btn {
  background: none;
  border: none;
  color: var(--color-text-muted);
  padding: 0.35rem 0.9rem;
  font-size: 0.82rem;
  font-weight: 500;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.tab-btn:hover {
  color: var(--color-text);
  background: rgba(255, 255, 255, 0.04);
}
.tab-btn.active {
  background: rgba(124, 58, 237, 0.15);
  color: var(--color-accent-light);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #4ade80;
  box-shadow: 0 0 8px rgba(74, 222, 128, 0.5);
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

.kbd-hint {
  font-size: 0.7rem;
  color: #374151;
}

.kbd-hint kbd {
  font-family: inherit;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--color-border);
  border-radius: 3px;
  padding: 0.05rem 0.3rem;
  font-size: 0.68rem;
}

/* ── Dashboard Grid ───────────────────────────── */
.dashboard {
  display: grid;
  grid-template-columns: 280px 1fr 380px;
  grid-template-rows: 1fr auto;
  gap: 1rem;
  padding: 1rem;
  min-height: 0;
  flex: 1;
  overflow: hidden;
}

.sidebar-col {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  overflow-y: auto;
  grid-row: 1;
  grid-column: 1;
}

.center-col {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-height: 0;
  grid-row: 1;
  grid-column: 2;
}

.graph-panel {
  height: 50%;
  min-height: 200px;
}

.log-col {
  display: flex;
  flex-direction: column;
  min-height: 0;
  grid-row: 1;
  grid-column: 3;
}

.bottom-bar {
  grid-column: 1 / -1;
  grid-row: 2;
}

/* ── Tab Content ──────────────────────────────── */
.tab-content {
  flex: 1;
  overflow-y: auto;
  max-width: 640px;
  margin: 0 auto;
  width: 100%;
  padding: 0;
}

/* ── Responsive ───────────────────────────────── */
@media (max-width: 1200px) {
  .dashboard {
    grid-template-columns: 260px 1fr;
  }
  .log-col {
    grid-column: 1 / -1;
    grid-row: 2;
    max-height: 300px;
  }
  .bottom-bar {
    grid-row: 3;
  }
}

@media (max-width: 800px) {
  .dashboard {
    grid-template-columns: 1fr;
  }
  .sidebar-col,
  .center-col,
  .log-col {
    grid-column: 1;
  }
  .center-col {
    grid-row: 2;
  }
  .log-col {
    grid-row: 3;
    max-height: 250px;
  }
  .bottom-bar {
    grid-row: 4;
  }
}
</style>
