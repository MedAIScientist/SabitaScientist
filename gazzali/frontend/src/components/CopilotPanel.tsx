import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

/** One entry in the conversation. Tool and confirm cards sit between the text turns. */
type Item =
  | { kind: 'user'; text: string }
  | { kind: 'assistant'; text: string }
  | { kind: 'tool'; label: string; ok: boolean | null; summary?: string; link?: string | null }
  | { kind: 'confirm'; name: string; label: string; args: Record<string, unknown>; state: 'pending' | 'approved' | 'cancelled' }
  | { kind: 'error'; text: string }

type Approve = { name: string; args: Record<string, unknown> }

const STORE_KEY = 'copilot_items'
const HISTORY_TURNS = 20

function loadItems(): Item[] {
  try { return JSON.parse(sessionStorage.getItem(STORE_KEY) || '[]') } catch { return [] }
}

/** Suggestions that fit the page the user is on. */
function starters(projectId: string | null): string[] {
  return projectId
    ? ['Summarize where this project stands', 'Which tasks are still open?', 'Suggest the next experiments to run', 'Add a task to review the related literature']
    : ['What are my projects?', 'Create a project for a new study', 'Find papers about retinal imaging', 'Which conferences have upcoming deadlines?']
}

/** Arguments shown on a confirm card, as readable "field: value" lines. */
function describeArgs(args: Record<string, unknown>): [string, string][] {
  return Object.entries(args)
    .filter(([, v]) => v !== '' && v !== null && v !== undefined)
    .map(([k, v]) => [k.replace(/_id$/, '').replace(/_/g, ' '), String(v)])
}

export function CopilotPanel({ onClose }: { onClose: () => void }) {
  const [items, setItems] = useState<Item[]>(loadItems)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const location = useLocation()
  const navigate = useNavigate()
  const projectId = location.pathname.match(/^\/projects\/([^/]+)/)?.[1] ?? null

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [items])
  useEffect(() => { try { sessionStorage.setItem(STORE_KEY, JSON.stringify(items)) } catch { /* private mode */ } }, [items])

  const push = (item: Item) => setItems(prev => [...prev, item])

  /** Append streamed text to the assistant turn in progress, or start one. */
  const appendText = (text: string) => setItems(prev => {
    const last = prev[prev.length - 1]
    if (last?.kind === 'assistant') return [...prev.slice(0, -1), { ...last, text: last.text + text }]
    return [...prev, { kind: 'assistant', text }]
  })

  async function stream(message: string, history: Item[], approve?: Approve) {
    setBusy(true)
    const controller = new AbortController()
    abortRef.current = controller
    const turns = history
      .filter((i): i is Extract<Item, { kind: 'user' | 'assistant' }> => i.kind === 'user' || i.kind === 'assistant')
      .slice(-HISTORY_TURNS)
      .map(i => ({ role: i.kind, content: i.text }))
    try {
      const token = sessionStorage.getItem('pm_token')
      const resp = await fetch('/api/v1/copilot/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ message, history: turns, approve, context: { page: location.pathname, project_id: projectId } }),
        signal: controller.signal,
      })
      if (!resp.ok || !resp.body) throw new Error(resp.status === 401 ? 'Your session expired. Please sign in again.' : `Request failed (${resp.status})`)
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() || ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          let ev: any
          try { ev = JSON.parse(line.slice(6)) } catch { continue }
          if (ev.type === 'token') appendText(ev.data)
          else if (ev.type === 'tool_start') push({ kind: 'tool', label: ev.label, ok: null })
          else if (ev.type === 'tool_end') setItems(prev => {
            // Complete the running card for this tool, or add a finished one (approved writes).
            const idx = prev.map(i => i.kind === 'tool' && i.ok === null && i.label === ev.label).lastIndexOf(true)
            const card: Item = { kind: 'tool', label: ev.label, ok: ev.ok, summary: ev.summary, link: ev.link }
            return idx === -1 ? [...prev, card] : [...prev.slice(0, idx), card, ...prev.slice(idx + 1)]
          })
          else if (ev.type === 'confirm') push({ kind: 'confirm', name: ev.name, label: ev.label, args: ev.args, state: 'pending' })
          else if (ev.type === 'error') push({ kind: 'error', text: ev.message })
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') push({ kind: 'error', text: err.message || 'Could not reach the assistant.' })
    } finally {
      setBusy(false)
      abortRef.current = null
    }
  }

  function send(text = input) {
    const msg = text.trim()
    if (!msg || busy) return
    setInput('')
    const next: Item[] = [...items, { kind: 'user', text: msg }]
    setItems(next)
    stream(msg, items)
  }

  function decide(index: number, approve: boolean) {
    const card = items[index]
    if (card.kind !== 'confirm' || card.state !== 'pending' || busy) return
    const next = items.map((it, i) => (i === index ? { ...card, state: approve ? 'approved' : 'cancelled' } as Item : it))
    setItems(next)
    if (approve) stream('', next, { name: card.name, args: card.args })
    else push({ kind: 'assistant', text: 'Cancelled — nothing was changed.' })
  }

  const hasPending = items.some(i => i.kind === 'confirm' && i.state === 'pending')

  return (
    <aside className="copilot" aria-label="AI copilot">
      <header className="copilot-head">
        <strong>AI copilot</strong>
        <span style={{ flex: 1 }} />
        {items.length > 0 && <button className="btn" style={{ height: 28 }} onClick={() => setItems([])} disabled={busy}>New chat</button>}
        <button className="icon-btn" onClick={onClose} aria-label="Close copilot">✕</button>
      </header>

      <div className="copilot-body">
        {items.length === 0 && (
          <div className="copilot-empty">
            <p>Ask about your projects, tasks, experiments and papers. I look things up for you, and ask before changing anything.</p>
            <div className="copilot-starters">
              {starters(projectId).map(s => <button key={s} className="btn" onClick={() => send(s)}>{s}</button>)}
            </div>
          </div>
        )}
        {items.map((it, i) => {
          if (it.kind === 'user') return <div key={i} className="msg msg-user">{it.text}</div>
          if (it.kind === 'assistant') return <div key={i} className="msg msg-ai">{it.text}</div>
          if (it.kind === 'error') return <div key={i} className="msg msg-error" role="alert">{it.text}</div>
          if (it.kind === 'tool') return (
            <div key={i} className="tool-card" data-state={it.ok === null ? 'running' : it.ok ? 'ok' : 'failed'}>
              <span className="tool-dot" aria-hidden />
              <span>{it.label}{it.ok === null ? '…' : ''}</span>
              {it.ok === false && it.summary && <span className="tool-note">{it.summary}</span>}
              {it.link && <a href={it.link} onClick={e => { e.preventDefault(); navigate(it.link!) }}>Open →</a>}
            </div>
          )
          return (
            <div key={i} className="confirm-card" data-state={it.state}>
              <div className="confirm-title">{it.label}?</div>
              <dl>{describeArgs(it.args).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
              {it.state === 'pending' ? (
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn btn-primary" onClick={() => decide(i, true)} disabled={busy}>Confirm</button>
                  <button className="btn" onClick={() => decide(i, false)} disabled={busy}>Cancel</button>
                </div>
              ) : <div className="tool-note">{it.state === 'approved' ? 'Approved' : 'Cancelled'}</div>}
            </div>
          )
        })}
        {busy && items[items.length - 1]?.kind !== 'assistant' && <div className="msg msg-ai typing" aria-label="Thinking">…</div>}
        <div ref={endRef} />
      </div>

      <form className="copilot-input" onSubmit={e => { e.preventDefault(); send() }}>
        <textarea
          value={input} rows={2}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder={hasPending ? 'Confirm or cancel the action above first' : 'Ask anything… (Shift+Enter for a new line)'}
          disabled={busy || hasPending}
        />
        {busy
          ? <button type="button" className="btn" onClick={() => abortRef.current?.abort()}>Stop</button>
          : <button type="submit" className="btn btn-primary" disabled={!input.trim() || hasPending}>Send</button>}
      </form>
    </aside>
  )
}
