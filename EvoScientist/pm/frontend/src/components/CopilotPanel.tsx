import { useState, useRef, useEffect, useCallback } from 'react'
import { useLocation } from 'react-router-dom'

interface ToolCall {
  name: string
  output: string
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  toolCalls?: ToolCall[]
}

function uuidv4(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16)
  })
}

function getSessionId(): string {
  let sid = sessionStorage.getItem('copilot_session')
  if (!sid) {
    sid = uuidv4()
    sessionStorage.setItem('copilot_session', sid)
  }
  return sid
}

export function CopilotPanel({ onClose }: { onClose: () => void }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const accRef = useRef('')
  const toolRef = useRef('')
  const abortRef = useRef<AbortController | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const location = useLocation()
  const [, forceUpdate] = useState(0)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, streaming])

  function buildContext() {
    const ctx: Record<string, string> = { page: location.pathname }
    const m = location.pathname.match(/^\/projects\/([^/]+)/)
    if (m) ctx.project_id = m[1]
    return ctx
  }

  const send = useCallback(async () => {
    const msg = input.trim()
    if (!msg || streaming) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: msg }])
    setStreaming(true)
    accRef.current = ''
    toolRef.current = ''
    forceUpdate(n => n + 1)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const token = sessionStorage.getItem('pm_token')
      const resp = await fetch('/api/v1/copilot/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ message: msg, session_id: getSessionId(), context: buildContext() }),
        signal: controller.signal,
      })
      const reader = resp.body?.getReader()
      if (!reader) return

      const decoder = new TextDecoder()
      let buf = ''
      const toolCalls: ToolCall[] = []

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const ev = JSON.parse(line.slice(6))
            if (ev.type === 'token') {
              accRef.current += ev.data
              forceUpdate(n => n + 1)
            } else if (ev.type === 'tool_start') {
              toolRef.current = `🔧 ${ev.data}...`
              forceUpdate(n => n + 1)
            } else if (ev.type === 'tool_end') {
              toolCalls.push({ name: toolCalls.length > 0 ? toolCalls[toolCalls.length - 1].name : 'tool', output: String(ev.data).slice(0, 200) })
              toolRef.current = ''
              forceUpdate(n => n + 1)
            } else if (ev.type === 'error') {
              accRef.current += `\n\nError: ${ev.data}`
              forceUpdate(n => n + 1)
            }
          } catch { /* skip */ }
        }
      }

      if (accRef.current.trim()) {
        setMessages(prev => [...prev, { role: 'assistant', content: accRef.current, toolCalls }])
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${err.message}` }])
      }
    } finally {
      setStreaming(false)
      accRef.current = ''
      toolRef.current = ''
      abortRef.current = null
      forceUpdate(n => n + 1)
    }
  }, [input, streaming, location.pathname])

  function cancelStream() {
    abortRef.current?.abort()
    if (accRef.current.trim()) {
      setMessages(prev => [...prev, { role: 'assistant', content: accRef.current }])
    }
    setStreaming(false)
    accRef.current = ''
    toolRef.current = ''
  }

  return (
    <div style={{
      position: 'fixed', right: 0, top: 48, bottom: 0, width: 420,
      background: 'var(--surface-panel)', borderLeft: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', zIndex: 50,
      fontFamily: 'system-ui, -apple-system, sans-serif',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 16px', borderBottom: '1px solid var(--border)',
      }}>
        <span style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>
          AI Copilot
        </span>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', cursor: 'pointer', fontSize: 20,
          color: 'var(--text-dim)', padding: '2px 6px', borderRadius: 4,
        }}>✕</button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
        {messages.length === 0 && !streaming && (
          <div style={{ color: 'var(--text-dim)', fontSize: 14, padding: 16, textAlign: 'center', lineHeight: 1.6 }}>
            I'm your AI research assistant.<br />
            Ask me to create projects, draft papers,<br />
            manage experiments, search publications,<br />
            or anything else in the platform.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: 12 }}>
            <div style={{
              fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)',
              color: m.role === 'user' ? '#ff8015' : 'var(--text-dim)',
              marginBottom: 3, letterSpacing: '0.06em',
            }}>{m.role === 'user' ? 'YOU' : 'COPILOT'}</div>
            <div style={{ fontSize: 15, lineHeight: 1.6, color: 'var(--text)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {m.content}
            </div>
            {m.toolCalls && m.toolCalls.length > 0 && (
              <details style={{ marginTop: 4 }}>
                <summary style={{ fontSize: 12, color: 'var(--text-dim)', cursor: 'pointer', fontFamily: 'var(--font-mono)' }}>
                  {m.toolCalls.length} tool call{m.toolCalls.length > 1 ? 's' : ''}
                </summary>
                {m.toolCalls.map((tc, j) => (
                  <pre key={j} style={{
                    fontSize: 12, background: 'var(--surface-input)', padding: 6, borderRadius: 4,
                    marginTop: 4, overflow: 'hidden', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
                  }}>{tc.output}</pre>
                ))}
              </details>
            )}
          </div>
        ))}
        {streaming && (
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', marginBottom: 3 }}>
              COPILOT
            </div>
            <div style={{ fontSize: 15, lineHeight: 1.6, color: 'var(--text)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {accRef.current || ''}<span style={{ animation: 'blink 1s infinite', color: '#ff8015' }}>▍</span>
            </div>
            {toolRef.current && (
              <div style={{ fontSize: 13, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 4, fontStyle: 'italic' }}>
                {toolRef.current}
              </div>
            )}
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div style={{ padding: '8px 12px 12px', borderTop: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
            placeholder="Ask the Copilot..."
            disabled={streaming}
            style={{
              flex: 1, padding: '8px 12px', fontSize: 15, outline: 'none',
              background: 'var(--surface-input)', border: '1px solid var(--border)',
              borderRadius: 6, color: 'var(--text)', fontFamily: 'var(--font-mono)',
            }}
          />
          {streaming ? (
            <button onClick={cancelStream} style={{
              padding: '8px 14px', cursor: 'pointer', fontSize: 14, fontWeight: 700,
              fontFamily: 'var(--font-mono)', background: 'transparent',
              border: '1px solid #f43f5e', borderRadius: 6, color: '#f43f5e',
            }}>STOP</button>
          ) : (
            <button onClick={send} disabled={!input.trim()} style={{
              padding: '8px 14px', cursor: input.trim() ? 'pointer' : 'default', fontSize: 14, fontWeight: 700,
              fontFamily: 'var(--font-mono)', background: input.trim() ? '#ff8015' : 'var(--surface-input)',
              border: 'none', borderRadius: 6, color: input.trim() ? '#fff' : 'var(--text-muted)',
              opacity: input.trim() ? 1 : 0.5,
            }}>SEND</button>
          )}
        </div>
      </div>

      <style>{`@keyframes blink { 50% { opacity: 0; } }`}</style>
    </div>
  )
}
