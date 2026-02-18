<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRunStore } from '@/stores/runStore'
import { useEventStore } from '@/stores/eventStore'
import { useWebSocket, type ConnectionState } from '@/composables/useWebSocket'

const runStore = useRunStore()
const eventStore = useEventStore()

const goal = ref('')
const cwd = ref('.')
const modelName = ref('claude-sonnet-4-6')
const maxIterations = ref(20)
const hitl = ref(false)
const loading = ref(false)
const errorMsg = ref('')

let wsRef: ReturnType<typeof useWebSocket> | null = null
const wsState = ref<ConnectionState>('disconnected')

const isRunning = computed(() => runStore.isRunning)

async function startRun() {
  if (!goal.value.trim()) return
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await fetch('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        goal: goal.value,
        cwd: cwd.value || '.',
        model_name: modelName.value,
        max_iterations: maxIterations.value,
        hitl_enabled: hitl.value,
      }),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail ?? 'Failed to start run')
    }
    const data = await res.json() as { run_id: string }
    const runId = data.run_id

    eventStore.clearForRun(runId)
    runStore.setActiveRun({
      runId,
      goal: goal.value,
      status: 'running',
      iteration: 0,
      maxIterations: maxIterations.value,
      modelName: modelName.value,
      goalReason: '',
      hitlEnabled: hitl.value,
      cwd: cwd.value || '.',
      startedAt: Date.now(),
    })

    wsRef = useWebSocket(runId)
    wsRef.connect()
    wsState.value = 'connecting'

    goal.value = ''
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function abortRun() {
  await runStore.abort()
}

const models = [
  { group: 'Anthropic', items: ['claude-sonnet-4-6', 'claude-opus-4', 'claude-3-5-haiku-latest'] },
  { group: 'OpenAI', items: ['gpt-4o', 'gpt-4o-mini', 'o1', 'o3', 'o4-mini'] },
  { group: 'Google', items: ['gemini/gemini-2.5-pro', 'gemini/gemini-2.5-flash'] },
  { group: 'Ollama', items: ['ollama/llama3.3', 'ollama/codellama', 'ollama/mistral'] },
]
</script>

<template>
  <div class="run-controls">
    <h2 class="section-title">🚀 New Run</h2>

    <div class="controls-form">
      <div class="form-row goal-row">
        <div class="input-group flex-1">
          <label>Goal (or blank for auto-detect)</label>
          <textarea
            v-model="goal"
            class="input textarea"
            placeholder="Describe what the agent should achieve…"
            rows="2"
            :disabled="isRunning"
            @keydown.ctrl.enter.prevent="startRun"
            @keydown.meta.enter.prevent="startRun"
          />
        </div>
      </div>

      <div class="form-row">
        <div class="input-group">
          <label>Working Directory</label>
          <input v-model="cwd" class="input" placeholder="." :disabled="isRunning" />
        </div>
        <div class="input-group">
          <label>Model</label>
          <select v-model="modelName" class="input" :disabled="isRunning">
            <optgroup v-for="group in models" :key="group.group" :label="group.group">
              <option v-for="m in group.items" :key="m" :value="m">{{ m }}</option>
            </optgroup>
          </select>
        </div>
      </div>

      <div class="form-row">
        <div class="input-group">
          <label>Max Iterations</label>
          <div class="slider-row">
            <input
              v-model.number="maxIterations"
              type="range"
              min="1"
              max="100"
              class="slider"
              :disabled="isRunning"
            />
            <span class="slider-val">{{ maxIterations }}</span>
          </div>
        </div>
        <div class="input-group">
          <label class="checkbox-label">
            <input v-model="hitl" type="checkbox" class="checkbox" :disabled="isRunning" />
            <span>Human-in-the-loop</span>
          </label>
        </div>
      </div>

      <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>

      <div class="btn-row">
        <button
          v-if="!isRunning"
          class="btn-start"
          :disabled="loading"
          @click="startRun"
        >
          <span v-if="loading" class="spinner" />
          <span v-else>▶ Start Run</span>
        </button>
        <button
          v-else
          class="btn-abort"
          @click="abortRun"
        >
          ■ Abort
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.run-controls {
  padding: 1.25rem;
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  backdrop-filter: blur(12px);
}

.section-title {
  margin: 0 0 1rem;
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-accent-light);
}

.controls-form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.form-row {
  display: flex;
  gap: 0.75rem;
}

.goal-row {
  flex-direction: column;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
}

.input-group label {
  font-size: 0.72rem;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.flex-1 { flex: 1; }

.input {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
  color: var(--color-text);
  font-size: 0.87rem;
  outline: none;
  transition: border-color 0.2s;
}
.input:focus {
  border-color: var(--color-accent);
}
.input::placeholder {
  color: #374151;
}
.input option, .input optgroup {
  background: #1a0533;
}

.textarea {
  resize: vertical;
  min-height: 48px;
  font-family: inherit;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.slider {
  flex: 1;
  accent-color: var(--color-accent);
}

.slider-val {
  min-width: 2rem;
  text-align: right;
  font-weight: 700;
  font-size: 0.9rem;
  color: var(--color-accent-light);
  font-family: 'JetBrains Mono', monospace;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.87rem;
  color: var(--color-text-muted);
  margin-top: 1.1rem;
}

.checkbox {
  accent-color: var(--color-accent);
  width: 1rem;
  height: 1rem;
}

.error-msg {
  color: #f87171;
  font-size: 0.85rem;
  margin: 0;
}

.btn-row {
  display: flex;
  gap: 0.5rem;
}

.btn-start {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.6rem;
  background: linear-gradient(135deg, #7c3aed, #4c0ee3);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.15s;
}
.btn-start:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}
.btn-start:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-abort {
  flex: 1;
  padding: 0.6rem;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  color: #f87171;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-abort:hover {
  background: rgba(239, 68, 68, 0.25);
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
  to { transform: rotate(360deg); }
}
</style>
