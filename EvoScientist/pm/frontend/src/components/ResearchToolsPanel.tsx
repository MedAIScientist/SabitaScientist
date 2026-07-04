import { useState } from 'react'
import { api } from '../api'

interface Props {
  projectId: string
  onClose: () => void
}

type ToolTab = 'hypothesis' | 'ideation' | 'methods' | 'citations'

export function ResearchToolsPanel({ projectId, onClose }: Props) {
  const [tab, setTab] = useState<ToolTab>('hypothesis')
  const [topic, setTopic] = useState('')
  const [context, setContext] = useState('')
  const [focusArea, setFocusArea] = useState('')
  const [ideaCount, setIdeaCount] = useState(5)
  const [methods, setMethods] = useState('')
  const [citations, setCitations] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      let res: { status: string; message: string }
      if (tab === 'hypothesis') {
        res = await api.generateHypothesis(projectId, topic, context || undefined)
      } else if (tab === 'ideation') {
        res = await api.researchIdeation(projectId, topic, focusArea || undefined, ideaCount)
      } else if (tab === 'methods') {
        res = await api.validateMethodology(projectId, methods)
      } else {
        res = await api.verifyCitations(projectId, citations)
      }
      setResult(res.message)
      setTopic(''); setContext(''); setFocusArea(''); setMethods(''); setCitations('')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  const accent = '#8b5cf6'
  const tabs: { key: ToolTab; label: string; description: string }[] = [
    { key: 'hypothesis', label: '🔬 Hypothesis', description: 'Generate testable hypotheses from a topic' },
    { key: 'ideation', label: '💡 Ideation', description: 'Explore novel research directions' },
    { key: 'methods', label: '🔍 Methods Review', description: 'Validate proposed experimental methods' },
    { key: 'citations', label: '📚 Citations', description: 'Verify citation plausibility' },
  ]

  const inputStyle: React.CSSProperties = {
    padding: '8px 11px', background: 'var(--surface-input)',
    border: '1px solid var(--border)', borderRadius: 6,
    color: 'var(--text)', fontSize: 18, outline: 'none', width: '100%', boxSizing: 'border-box',
  }

  return (
    <div style={{
      position: 'fixed', right: 0, top: 0, bottom: 0, width: 400,
      background: 'var(--surface-panel)', borderLeft: '1px solid var(--border)',
      zIndex: 31, display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      <div style={{
        padding: '12px 14px 10px', borderBottom: '1px solid var(--border-subtle)',
        flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <span style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color: accent, letterSpacing: '0.08em' }}>
          🧪 AI RESEARCH TOOLS
        </span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-3)', fontSize: 22, cursor: 'pointer', padding: 2 }}>✕</button>
      </div>

      <div style={{ display: 'flex', gap: 2, padding: '6px 8px', borderBottom: '1px solid var(--border-subtle)', flexShrink: 0 }}>
        {tabs.map(t => (
          <button key={t.key} onClick={() => { setTab(t.key); setResult(null); setError(null) }} style={{
            flex: 1, padding: '5px 4px', cursor: 'pointer', fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 700,
            background: tab === t.key ? `${accent}14` : 'transparent',
            border: `1px solid ${tab === t.key ? `${accent}44` : 'transparent'}`,
            borderRadius: 4, color: tab === t.key ? accent : 'var(--text-3)', letterSpacing: '0.04em',
          }}>{t.key === 'hypothesis' ? '🔬' : t.key === 'ideation' ? '💡' : t.key === 'methods' ? '🔍' : '📚'}</button>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '10px 14px' }}>
        <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-heading)', marginBottom: 4 }}>{tabs.find(t => t.key === tab)?.label}</div>
        <div style={{ fontSize: 15, color: 'var(--text-dim)', marginBottom: 14 }}>{tabs.find(t => t.key === tab)?.description}</div>

        {tab === 'hypothesis' && (
          <>
            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>TOPIC *</label>
              <input value={topic} onChange={e => setTopic(e.target.value)} placeholder="e.g. Role of X in Y pathway" style={inputStyle} />
            </div>
            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>CONTEXT (optional)</label>
              <textarea value={context} onChange={e => setContext(e.target.value)} placeholder="Prior results, constraints, or background…" rows={4} style={{ ...inputStyle, resize: 'vertical' }} />
            </div>
          </>
        )}

        {tab === 'ideation' && (
          <>
            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>RESEARCH TOPIC *</label>
              <input value={topic} onChange={e => setTopic(e.target.value)} placeholder="e.g. Neural mechanisms of learning" style={inputStyle} />
            </div>
            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>FOCUS AREA (optional)</label>
              <input value={focusArea} onChange={e => setFocusArea(e.target.value)} placeholder="e.g. Reinforcement learning, hippocampus" style={inputStyle} />
            </div>
            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>NUMBER OF IDEAS</label>
              <select value={ideaCount} onChange={e => setIdeaCount(Number(e.target.value))} style={inputStyle}>
                {[3, 5, 10, 15, 20].map(n => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
          </>
        )}

        {tab === 'methods' && (
          <div style={{ marginBottom: 10 }}>
            <label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>PROPOSED METHODS *</label>
            <textarea value={methods} onChange={e => setMethods(e.target.value)}
              placeholder="Describe your experimental design, protocols, controls, and analysis plan in detail…"
              rows={8} style={{ ...inputStyle, resize: 'vertical', fontSize: 17 }} />
          </div>
        )}

        {tab === 'citations' && (
          <div style={{ marginBottom: 10 }}>
            <label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>CITATIONS *</label>
            <textarea value={citations} onChange={e => setCitations(e.target.value)}
              placeholder="Paste your references/bibliography here. The AI will check each for plausibility and flag concerns."
              rows={8} style={{ ...inputStyle, resize: 'vertical', fontSize: 17 }} />
          </div>
        )}

        <button onClick={handleSubmit} disabled={loading}
          style={{
            width: '100%', padding: '8px 0', cursor: loading ? 'default' : 'pointer',
            background: loading ? `${accent}07` : `${accent}12`,
            border: `1px solid ${accent}44`, borderRadius: 6,
            color: accent, fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
            marginBottom: 10,
          }}
        >{loading ? 'GENERATING…' : 'RUN'}</button>

        {error && (
          <div style={{ padding: '8px 10px', background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.2)', borderRadius: 6, color: '#f43f5e', fontSize: 15, marginBottom: 10 }}>{error}</div>
        )}

        {result && (
          <div style={{ padding: '8px 10px', background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', borderRadius: 6, color: '#10b981', fontSize: 15 }}>
            {result}
          </div>
        )}
      </div>
    </div>
  )
}
