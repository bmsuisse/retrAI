<script setup lang="ts">
import { useRunStore } from '@/stores/runStore'

const runStore = useRunStore()

async function respond(decision: 'approve' | 'abort') {
  const runId = runStore.activeRun?.runId
  if (!runId) return

  await fetch(`/api/runs/${runId}/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision }),
  })

  runStore.setAwaitingHuman(false)
}
</script>

<template>
  <Teleport to="body">
    <div v-if="runStore.awaitingHuman" class="modal-backdrop">
      <div class="modal">
        <div class="modal-icon">👤</div>
        <h2 class="modal-title">Human Check Required</h2>
        <p class="modal-body">
          The agent has paused and is waiting for your approval before continuing.
        </p>
        <div class="modal-actions">
          <button class="btn-approve" @click="respond('approve')">
            ✓ Approve & Continue
          </button>
          <button class="btn-abort" @click="respond('abort')">
            ✗ Abort Run
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(5, 11, 31, 0.8);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fade-in 0.2s ease;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.modal {
  background: linear-gradient(135deg, #1a0533, #0f0a2e);
  border: 1px solid rgba(124, 58, 237, 0.5);
  border-radius: 16px;
  padding: 2.5rem;
  max-width: 400px;
  width: 90%;
  text-align: center;
  box-shadow: 0 0 60px rgba(124, 58, 237, 0.3);
  animation: slide-up 0.3s ease;
}

@keyframes slide-up {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.modal-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.modal-title {
  margin: 0 0 0.75rem;
  font-size: 1.3rem;
  font-weight: 700;
  color: #a78bfa;
}

.modal-body {
  color: var(--color-text-muted);
  font-size: 0.95rem;
  margin-bottom: 2rem;
  line-height: 1.6;
}

.modal-actions {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.btn-approve {
  padding: 0.75rem;
  background: linear-gradient(135deg, #16a34a, #15803d);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}
.btn-approve:hover {
  opacity: 0.9;
}

.btn-abort {
  padding: 0.75rem;
  background: transparent;
  border: 1px solid #ef4444;
  border-radius: 8px;
  color: #f87171;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-abort:hover {
  background: rgba(239, 68, 68, 0.1);
}
</style>
