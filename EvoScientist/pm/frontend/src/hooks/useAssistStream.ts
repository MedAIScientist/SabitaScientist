import { useEffect, useRef, useState } from 'react'

export type AssistStreamStatus = 'idle' | 'streaming' | 'done' | 'failed' | 'cancelled'

export interface AssistStreamState {
  output: string
  isStreaming: boolean
  streamStatus: AssistStreamStatus
}

/**
 * Streams SSE output for an experiment assist.
 * Resets state whenever assistId changes.
 */
export function useAssistStream(assistId: string | null): AssistStreamState {
  const [output, setOutput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamStatus, setStreamStatus] = useState<AssistStreamStatus>('idle')
  const controllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    setOutput('')
    setIsStreaming(false)
    setStreamStatus('idle')

    if (!assistId) return

    const controller = new AbortController()
    controllerRef.current = controller
    setIsStreaming(true)
    setStreamStatus('streaming')

    async function stream() {
      const token = sessionStorage.getItem('pm_token')
      let response: Response

      try {
        response = await fetch(`/api/v1/assists/${assistId}/stream`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: controller.signal,
        })
      } catch {
        if (!controller.signal.aborted) {
          setIsStreaming(false)
          setStreamStatus('failed')
        }
        return
      }

      if (!response.ok) {
        setIsStreaming(false)
        setStreamStatus('failed')
        return
      }

      const reader = response.body?.getReader()
      if (!reader) { setIsStreaming(false); setStreamStatus('failed'); return }

      const decoder = new TextDecoder()
      let buffer = ''

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const event = JSON.parse(line.slice(6)) as { type: string; data: string }
              if (event.type === 'token') {
                setOutput(prev => prev + event.data)
              } else if (event.type === 'status') {
                setStreamStatus(event.data as AssistStreamStatus)
                setIsStreaming(false)
              } else if (event.type === 'error') {
                setStreamStatus('failed')
                setIsStreaming(false)
              }
            } catch { /* malformed SSE line — ignore */ }
          }
        }
      } catch {
        if (!controller.signal.aborted) {
          setIsStreaming(false)
          setStreamStatus('failed')
        }
      }
    }

    stream()

    return () => {
      controller.abort()
      controllerRef.current = null
    }
  }, [assistId])

  return { output, isStreaming, streamStatus }
}
