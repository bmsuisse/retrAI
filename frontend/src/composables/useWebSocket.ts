import { ref, onUnmounted } from 'vue'
import { useRunStore } from '@/stores/runStore'
import { useEventStore } from '@/stores/eventStore'

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error'

export function useWebSocket(runId: string) {
  const runStore = useRunStore()
  const eventStore = useEventStore()
  const connectionState = ref<ConnectionState>('disconnected')
  let ws: WebSocket | null = null
  let reconnectAttempts = 0
  const maxReconnectAttempts = 5

  function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/api/ws/${runId}`

    connectionState.value = 'connecting'
    ws = new WebSocket(url)

    ws.onopen = () => {
      connectionState.value = 'connected'
      reconnectAttempts = 0
    }

    ws.onmessage = (evt) => {
      let data: Record<string, unknown>
      try {
        data = JSON.parse(evt.data)
      } catch {
        return
      }

      const event = data as {
        kind: string
        run_id: string
        iteration: number
        payload: Record<string, unknown>
        ts: number
      }

      eventStore.addEvent({
        kind: event.kind as never,
        run_id: event.run_id,
        iteration: event.iteration,
        payload: event.payload,
        ts: event.ts,
      })

      handleEvent(event)
    }

    ws.onerror = () => {
      connectionState.value = 'error'
    }

    ws.onclose = () => {
      connectionState.value = 'disconnected'
      if (
        runStore.isRunning &&
        reconnectAttempts < maxReconnectAttempts
      ) {
        reconnectAttempts++
        const delay = Math.min(1000 * 2 ** reconnectAttempts, 16000)
        setTimeout(connect, delay)
      }
    }
  }

  function handleEvent(event: Record<string, unknown>) {
    const kind = event.kind as string
    const payload = (event.payload || {}) as Record<string, unknown>
    const iteration = event.iteration as number

    if (kind === 'iteration_complete') {
      runStore.updateIteration(runId, iteration)
    } else if (kind === 'goal_check') {
      const reason = payload.reason as string
      const achieved = payload.achieved as boolean
      if (achieved) {
        runStore.updateStatus(runId, 'achieved', reason)
      }
    } else if (kind === 'human_check_required') {
      runStore.setAwaitingHuman(true)
    } else if (kind === 'human_check_response') {
      runStore.setAwaitingHuman(false)
    } else if (kind === 'run_end') {
      const status = payload.status as string
      const reason = payload.reason as string
      if (status === 'aborted') {
        runStore.updateStatus(runId, 'aborted', reason)
      } else {
        runStore.updateStatus(
          runId,
          status === 'achieved' ? 'achieved' : 'failed',
          reason,
        )
      }
      runStore.setAwaitingHuman(false)
    } else if (kind === 'error') {
      runStore.updateStatus(runId, 'failed', payload.error as string)
    }
  }

  function disconnect() {
    reconnectAttempts = maxReconnectAttempts
    ws?.close()
    ws = null
  }

  onUnmounted(disconnect)

  return { connectionState, connect, disconnect }
}
