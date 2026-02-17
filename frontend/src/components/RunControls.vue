<script setup lang="ts">
import { ref } from 'vue'
import { useRunStore } from '@/stores/runStore'
import { useEventStore } from '@/stores/eventStore'
import { useWebSocket } from '@/composables/useWebSocket'

const runStore = useRunStore()
const eventStore = useEventStore()

const goal = ref('pytest')
const cwd = ref('.')
const model = ref('claude-sonnet-4-6')
const maxIter = ref(20)
const hitl = ref(false)
const loading = ref(false)
const errorMsg = ref('')
const wsRef = ref<ReturnType<typeof useWebSocket> | null>(null)

async function startRun() {
  loading.value = true
  errorMsg.value = ''

  try {
    const res = await fetch('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        goal: goal.value,
        cwd: cwd.value,
        model_name: model.value,
        max_iterations: maxIter.value,
        hitl_enabled: hitl.value,
      }),
    })

    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Failed to start run')
    }

    const data = await res.json()
    const runId = data.run_id

    eventStore.clearForRun(runId)
    runStore.setActiveRun({
      runId,
      goal: goal.value,
      status: 'running',
      iteration: 0,
      maxIterations: maxIter.value,
      modelName: model.value,
      goalReason: '',
      hitlEnabled: hitl.value,
      cwd: cwd.value,
    })

    // Connect WebSocket
    const ws = useWebSocket(runId)
    wsRef.value = ws
    ws.connect()
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="run-controls">
    <h2 class="section-title">New Run</h2>

    <div class="form-grid">
      <div class="form-group">
        <label>Goal</label>
        <select v-model="goal" class="input">
          <option value="pytest">pytest — fix failing tests</option>
          <option value="pyright">pyright — fix type errors</option>
          <option value="bun-test">bun-test — fix Bun/JS tests</option>
          <option value="npm-test">npm-test — fix npm test suite</option>
          <option value="cargo-test">cargo-test — fix Rust tests</option>
          <option value="go-test">go-test — fix Go tests</option>
          <option value="make-test">make-test — fix Makefile tests</option>
          <option value="shell-goal">shell-goal — custom command (.retrai.yml)</option>
          <option value="perf-check">perf-check — optimise under time limit</option>
          <option value="sql-benchmark">sql-benchmark — tune a SQL query</option>
          <option value="ai-eval">ai-eval — AI evaluation harness</option>
        </select>
      </div>

      <div class="form-group">
        <label>Project Directory</label>
        <input v-model="cwd" class="input" placeholder="." />
      </div>

      <div class="form-group">
        <label>Model</label>
        <input v-model="model" class="input" placeholder="claude-sonnet-4-6" />
      </div>

      <div class="form-group">
        <label>Max Iterations</label>
        <input v-model.number="maxIter" type="number" min="1" max="100" class="input" />
      </div>
    </div>

    <div class="form-row">
      <label class="checkbox-label">
        <input v-model="hitl" type="checkbox" class="checkbox" />
        <span>Human-in-the-loop (HITL)</span>
      </label>
    </div>

    <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>

    <button
      class="btn-primary"
      :disabled="loading || runStore.isRunning"
      @click="startRun"
    >
      <span v-if="loading" class="spinner" />
      <span v-else>{{ runStore.isRunning ? 'Running…' : '▶ Start Run' }}</span>
    </button>
  </div>
</template>

<style scoped>
.run-controls {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 1.5rem;
  backdrop-filter: blur(12px);
}

.section-title {
  margin: 0 0 1.25rem;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-accent-light);
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.form-group label {
  font-size: 0.8rem;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.input {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
  color: var(--color-text);
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.2s;
}
.input:focus {
  border-color: var(--color-accent);
}
.input option {
  background: #1a0533;
}

.form-row {
  margin-bottom: 1.25rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--color-text-muted);
}

.checkbox {
  accent-color: var(--color-accent);
  width: 1rem;
  height: 1rem;
}

.error-msg {
  color: #f87171;
  font-size: 0.85rem;
  margin-bottom: 0.75rem;
}

.btn-primary {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.65rem 1.25rem;
  background: linear-gradient(135deg, #7c3aed, #4c0ee3);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.1s;
}
.btn-primary:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}
.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spinner {
  width: 1rem;
  height: 1rem;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
