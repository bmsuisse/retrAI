import { defineStore } from 'pinia'
import { ref } from 'vue'

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
  const maxEvents = 1000

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

  return { events, addEvent, clearForRun, clearAll }
})
