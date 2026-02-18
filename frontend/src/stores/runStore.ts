import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type RunStatus = 'idle' | 'running' | 'achieved' | 'failed' | 'aborted'

export interface RunState {
  runId: string
  goal: string
  status: RunStatus
  iteration: number
  maxIterations: number
  modelName: string
  goalReason: string
  hitlEnabled: boolean
  cwd: string
  startedAt: number
}

export const useRunStore = defineStore('run', () => {
  const activeRun = ref<RunState | null>(null)
  const allRuns = ref<RunState[]>([])

  const isRunning = computed(() => activeRun.value?.status === 'running')
  const awaitingHuman = ref(false)
  const activeTab = ref<'dashboard' | 'history' | 'settings'>('dashboard')

  const elapsedSeconds = ref(0)
  let elapsedTimer: ReturnType<typeof setInterval> | null = null

  function startElapsedTimer() {
    stopElapsedTimer()
    elapsedSeconds.value = 0
    elapsedTimer = setInterval(() => {
      if (activeRun.value?.status === 'running') {
        elapsedSeconds.value = Math.floor(
          (Date.now() - activeRun.value.startedAt) / 1000,
        )
      }
    }, 1000)
  }

  function stopElapsedTimer() {
    if (elapsedTimer) {
      clearInterval(elapsedTimer)
      elapsedTimer = null
    }
  }

  const elapsedFormatted = computed(() => {
    const s = elapsedSeconds.value
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}:${sec.toString().padStart(2, '0')}`
  })

  function setActiveRun(run: RunState) {
    activeRun.value = run
    const idx = allRuns.value.findIndex((r) => r.runId === run.runId)
    if (idx >= 0) allRuns.value[idx] = run
    else allRuns.value.unshift(run)
    if (run.status === 'running') startElapsedTimer()
  }

  function updateStatus(runId: string, status: RunStatus, reason?: string) {
    if (activeRun.value?.runId === runId) {
      activeRun.value.status = status
      if (reason !== undefined) activeRun.value.goalReason = reason
    }
    const run = allRuns.value.find((r) => r.runId === runId)
    if (run) {
      run.status = status
      if (reason !== undefined) run.goalReason = reason
    }
    if (status !== 'running') stopElapsedTimer()
  }

  function updateIteration(runId: string, iteration: number) {
    if (activeRun.value?.runId === runId) {
      activeRun.value.iteration = iteration
    }
  }

  function setAwaitingHuman(val: boolean) {
    awaitingHuman.value = val
  }

  function clearActive() {
    activeRun.value = null
    awaitingHuman.value = false
    stopElapsedTimer()
  }

  async function abort() {
    const runId = activeRun.value?.runId
    if (!runId) return
    await fetch(`/api/runs/${runId}/abort`, { method: 'POST' })
  }

  async function fetchHistory() {
    const res = await fetch('/api/runs')
    if (!res.ok) return
    const data = (await res.json()) as Array<{
      run_id: string
      goal: string
      status: string
      model_name: string
      max_iterations: number
      cwd: string
    }>
    allRuns.value = data.map((r) => ({
      runId: r.run_id,
      goal: r.goal,
      status: r.status as RunStatus,
      iteration: 0,
      maxIterations: r.max_iterations,
      modelName: r.model_name,
      goalReason: '',
      hitlEnabled: false,
      cwd: r.cwd,
      startedAt: 0,
    }))
  }

  return {
    activeRun,
    allRuns,
    isRunning,
    awaitingHuman,
    activeTab,
    elapsedSeconds,
    elapsedFormatted,
    setActiveRun,
    updateStatus,
    updateIteration,
    setAwaitingHuman,
    clearActive,
    abort,
    fetchHistory,
  }
})
