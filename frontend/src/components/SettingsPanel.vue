<script setup lang="ts">
import { ref } from 'vue'
import { useRunStore } from '@/stores/runStore'

const runStore = useRunStore()

const model = ref('')
const maxIter = ref(20)
const hitl = ref(false)
const saving = ref(false)
const saved = ref(false)
const errorMsg = ref('')

function loadCurrent() {
  const run = runStore.activeRun
  if (!run) return
  model.value = run.modelName
  maxIter.value = run.maxIterations
  hitl.value = run.hitlEnabled
}

loadCurrent()

async function applySettings() {
  const runId = runStore.activeRun?.runId
  if (!runId) return
  saving.value = true
  errorMsg.value = ''
  saved.value = false
  try {
    const res = await fetch(`/api/runs/${runId}/config`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model_name: model.value || undefined,
        max_iterations: maxIter.value,
        hitl_enabled: hitl.value,
      }),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Failed to update')
    }
    saved.value = true
    setTimeout(() => { saved.value = false }, 2500)
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    saving.value = false
  }
}

const models = [
  { group: 'Anthropic', items: ['claude-sonnet-4-6', 'claude-opus-4', 'claude-3-5-haiku-latest'] },
  { group: 'OpenAI', items: ['gpt-4o', 'gpt-4o-mini', 'o1', 'o3', 'o4-mini'] },
  { group: 'Google', items: ['gemini/gemini-2.5-pro', 'gemini/gemini-2.5-flash'] },
  { group: 'Ollama', items: ['ollama/llama3.3', 'ollama/codellama', 'ollama/mistral'] },
]
</script>

<template>
  <div class="settings-panel">
    <h2 class="section-title">⚙️ Settings</h2>
    <p v-if="!runStore.activeRun" class="no-run">Start a run to adjust settings.</p>

    <div v-else class="settings-form">
      <div class="form-group">
        <label>Model</label>
        <select v-model="model" class="input">
          <optgroup v-for="group in models" :key="group.group" :label="group.group">
            <option v-for="m in group.items" :key="m" :value="m">{{ m }}</option>
          </optgroup>
        </select>
      </div>

      <div class="form-group">
        <label>Max Iterations</label>
        <div class="slider-row">
          <input
            v-model.number="maxIter"
            type="range"
            min="1"
            max="100"
            class="slider"
          />
          <span class="slider-val">{{ maxIter }}</span>
        </div>
      </div>

      <div class="form-group">
        <label class="checkbox-label">
          <input v-model="hitl" type="checkbox" class="checkbox" />
          <span>Human-in-the-loop</span>
        </label>
      </div>

      <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>

      <button
        class="btn-apply"
        :disabled="saving"
        @click="applySettings"
      >
        <span v-if="saving" class="spinner" />
        <span v-else-if="saved">✓ Saved</span>
        <span v-else>Apply Changes</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.settings-panel {
  padding: 1.5rem;
}

.section-title {
  margin: 0 0 1.25rem;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-accent-light);
}

.no-run {
  color: var(--color-text-muted);
  font-size: 0.9rem;
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
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
.input option, .input optgroup {
  background: #1a0533;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.slider {
  flex: 1;
  accent-color: var(--color-accent);
  height: 4px;
}

.slider-val {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--color-accent-light);
  font-family: 'JetBrains Mono', monospace;
  min-width: 2rem;
  text-align: right;
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
  margin: 0;
}

.btn-apply {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.6rem;
  background: linear-gradient(135deg, #7c3aed, #4c0ee3);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}
.btn-apply:hover:not(:disabled) {
  opacity: 0.9;
}
.btn-apply:disabled {
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
  to { transform: rotate(360deg); }
}
</style>
