import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { AiJobList } from './AiJobList'

interface Props {
  projectId: string
  onClose: () => void
}

type ToolTab = 'hypothesis' | 'ideation' | 'methods' | 'citations'

const TABS: { key: ToolTab; label: string; description: string }[] = [
  { key: 'hypothesis', label: 'Hypotheses', description: 'Generate 3–5 testable hypotheses from a topic.' },
  { key: 'ideation', label: 'Ideas', description: 'Explore new research directions around a topic.' },
  { key: 'methods', label: 'Methods review', description: 'Get a critical review of a proposed experimental design.' },
  { key: 'citations', label: 'Citations', description: 'Check references against Semantic Scholar and flag doubtful ones.' },
]

/**
 * AI research tools for one project. Each run is a background job: the list at
 * the bottom shows it working, then links to the saved result or says why it failed.
 */
export function ResearchToolsPanel({ projectId, onClose }: Props) {
  const qc = useQueryClient()
  const [tab, setTab] = useState<ToolTab>('hypothesis')
  const [topic, setTopic] = useState('')
  const [context, setContext] = useState('')
  const [focusArea, setFocusArea] = useState('')
  const [ideaCount, setIdeaCount] = useState(5)
  const [methods, setMethods] = useState('')
  const [citations, setCitations] = useState('')
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const ready = tab === 'methods' ? methods.trim() : tab === 'citations' ? citations.trim() : topic.trim()

  async function handleSubmit() {
    if (!ready) return
    setLoading(true)
    setError(null)
    setNotice(null)
    try {
      const res =
        tab === 'hypothesis' ? await api.generateHypothesis(projectId, topic, context || undefined)
        : tab === 'ideation' ? await api.researchIdeation(projectId, topic, focusArea || undefined, ideaCount)
        : tab === 'methods' ? await api.validateMethodology(projectId, methods)
        : await api.verifyCitations(projectId, citations)
      setNotice(`${res.message} You can keep working — the result appears below when it is ready.`)
      setTopic(''); setContext(''); setFocusArea(''); setMethods(''); setCitations('')
      qc.invalidateQueries({ queryKey: ['ai-jobs'] })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  const current = TABS.find(t => t.key === tab)!

  return (
    <aside className="copilot" aria-label="AI research tools">
      <header className="copilot-head">
        <strong>AI research tools</strong>
        <span style={{ flex: 1 }} />
        <button className="icon-btn" onClick={onClose} aria-label="Close research tools">✕</button>
      </header>

      <nav className="tabs" style={{ padding: '0 10px', borderBottom: '1px solid var(--border)', marginTop: 0 }}>
        {TABS.map(t => (
          <a key={t.key} href="#" className="tab" aria-current={tab === t.key ? 'page' : undefined}
            onClick={e => { e.preventDefault(); setTab(t.key); setNotice(null); setError(null) }}>{t.label}</a>
        ))}
      </nav>

      <div className="copilot-body">
        <p style={{ fontSize: 13.5, color: 'var(--text-2)' }}>{current.description}</p>

        {(tab === 'hypothesis' || tab === 'ideation') && (
          <label className="field"><span>{tab === 'hypothesis' ? 'Topic' : 'Research topic'}</span>
            <input className="input" value={topic} onChange={e => setTopic(e.target.value)}
              placeholder={tab === 'hypothesis' ? 'e.g. Role of X in Y pathway' : 'e.g. Retinal biomarkers of dementia'} />
          </label>
        )}
        {tab === 'hypothesis' && (
          <label className="field"><span>Context (optional)</span>
            <textarea className="input" rows={4} value={context} onChange={e => setContext(e.target.value)}
              placeholder="Prior results, constraints or background. Leave empty to use the project description." />
          </label>
        )}
        {tab === 'ideation' && (
          <>
            <label className="field"><span>Focus area (optional)</span>
              <input className="input" value={focusArea} onChange={e => setFocusArea(e.target.value)} placeholder="e.g. Self-supervised learning" />
            </label>
            <label className="field"><span>Number of ideas</span>
              <select className="input" value={ideaCount} onChange={e => setIdeaCount(Number(e.target.value))}>
                {[3, 5, 10, 15, 20].map(n => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
          </>
        )}
        {tab === 'methods' && (
          <label className="field"><span>Proposed methods</span>
            <textarea className="input" rows={8} value={methods} onChange={e => setMethods(e.target.value)}
              placeholder="Design, protocols, controls and analysis plan…" />
          </label>
        )}
        {tab === 'citations' && (
          <label className="field"><span>References</span>
            <textarea className="input" rows={8} value={citations} onChange={e => setCitations(e.target.value)}
              placeholder="Paste your reference list, one per line." />
          </label>
        )}

        <button className="btn btn-primary" style={{ justifyContent: 'center' }} onClick={handleSubmit} disabled={loading || !ready}>
          {loading ? 'Starting…' : `Run ${current.label.toLowerCase()}`}
        </button>

        {error && <div className="msg msg-error" role="alert">{error}</div>}
        {notice && <div className="tool-card" data-state="ok"><span className="tool-dot" aria-hidden /><span>{notice}</span></div>}

        <AiJobList projectId={projectId} />
      </div>
    </aside>
  )
}
