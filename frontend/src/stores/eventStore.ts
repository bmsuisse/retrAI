import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type EventKind =
  | 'step_start'
  | 'tool_call'
  | 'tool_result'
  | 'goal_check'
  | 'human_check_required'
  | 'human_check_response'
  | 'iteration_complete'
  | 'run_end'
  | 'error'
  | 'log'
  | 'llm_usage'
  | 'reasoning'
  | 'step_progress'

export interface AgentEvent {
  kind: EventKind
  run_id: string
  iteration: number
  payload: Record<string, unknown>
  ts: number
  id: string
}

export const useEventStore = defineStore('events', () => {
  const events = ref<AgentEvent[]>([])
  const maxEvents = 2000
  const selectedIteration = ref<number | null>(null)

  function addEvent(raw: Omit<AgentEvent, 'id'>) {
    const event: AgentEvent = { ...raw, id: `${raw.ts}-${Math.random()}` }
    events.value.push(event)
    if (events.value.length > maxEvents) {
      events.value.splice(0, events.value.length - maxEvents)
    }
  }

  function clearForRun(runId: string) {
    events.value = events.value.filter((e) => e.run_id !== runId)
  }

  function clearAll() {
    events.value = []
  }

  function setSelectedIteration(iter: number | null) {
    selectedIteration.value = iter
  }

  const filteredEvents = computed(() => {
    if (selectedIteration.value === null) return events.value
    return events.value.filter((e) => e.iteration === selectedIteration.value)
  })

  const reasoningEvents = computed(() =>
    events.value.filter((e) => e.kind === 'reasoning'),
  )

  const toolCallEvents = computed(() =>
    events.value.filter((e) => e.kind === 'tool_call'),
  )

  const goalCheckEvents = computed(() =>
    events.value.filter((e) => e.kind === 'goal_check'),
  )

  const llmUsageEvents = computed(() =>
    events.value.filter((e) => e.kind === 'llm_usage'),
  )

  const iterationGroups = computed(() => {
    const groups = new Map<number, AgentEvent[]>()
    for (const e of events.value) {
      const iter = e.iteration
      if (!groups.has(iter)) groups.set(iter, [])
      groups.get(iter)!.push(e)
    }
    return groups
  })

  const latestReasoning = computed(() => {
    const r = reasoningEvents.value
    if (r.length === 0) return null
    return r[r.length - 1]
  })

  return {
    events,
    selectedIteration,
    filteredEvents,
    reasoningEvents,
    toolCallEvents,
    goalCheckEvents,
    llmUsageEvents,
    iterationGroups,
    latestReasoning,
    addEvent,
    clearForRun,
    clearAll,
    setSelectedIteration,
  }
})
