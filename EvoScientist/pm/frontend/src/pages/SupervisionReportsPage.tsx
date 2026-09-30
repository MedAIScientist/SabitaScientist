import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { supervisionApi, api, WeeklyReport } from '../api'
import { useAuth } from '../auth'

export function SupervisionReportsPage() {
  const { role, isAdmin } = useAuth()
  const qc = useQueryClient()
  const [filters, setFilters] = useState({ status: '', review_status: '', risk_level: '' })
  const [active, setActive] = useState<WeeklyReport | null>(null)
  const [feedback, setFeedback] = useState('')
  const [msg, setMsg] = useState<string | null>(null)

  const canReview = role === 'professor' || isAdmin

  const { data: reports, isLoading } = useQuery({
    queryKey: ['supervision-reports', filters],
    queryFn: () => supervisionApi.listReports({
      status: filters.status || undefined,
      review_status: filters.review_status || undefined,
      risk_level: filters.risk_level || undefined,
    }),
  })

  const { data: mine } = useQuery({
    queryKey: ['my-reports'],
    queryFn: () => supervisionApi.listReports(),
    enabled: !canReview,
  })

  const { data: users } = useQuery({ queryKey: ['users'], queryFn: () => api.listUsers() })
  const nameOf = (id: string) => users?.find(u => u.id === id)?.username || id

  async function saveReview() {
    if (!active) return
    try {
      await supervisionApi.reviewReport(active.id, {
        review_status: active.review_status,
        feedback: feedback || undefined,
        risk_override: active.risk_override || undefined,
      })
      setMsg('Review saved.')
      await qc.invalidateQueries({ queryKey: ['supervision-reports'] })
    } catch (e: any) {
      setMsg(e.message)
    }
  }

  if (!canReview) {
    return (
      <div style={{ padding: 28 }}>
        <h1 style={{ fontSize: 17, color: 'var(--text-heading)' }}>My weekly history</h1>
        {(mine || []).map(r => (
          <div key={r.id} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 14, marginBottom: 10 }}>
            <strong>{r.week_start}</strong> · {r.status} · review: {r.review_status}
            {r.feedback && <div style={{ marginTop: 6, color: 'var(--text-2)' }}>Feedback: {r.feedback}</div>}
          </div>
        ))}
        {!mine?.length && <p style={{ color: 'var(--text-2)' }}>No reports yet. Submit a weekly update first.</p>}
      </div>
    )
  }

  return (
    <div style={{ padding: '24px 32px' }}>
      <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', color: 'var(--text-dim)' }}>Weekly supervision</div>
      <h1 style={{ margin: '4px 0 16px', fontSize: 22, color: 'var(--text-heading)' }}>Reports</h1>

      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
        <select value={filters.status} onChange={e => setFilters(f => ({ ...f, status: e.target.value }))} style={inputStyle}>
          <option value="">Status…</option>
          {['draft', 'submitted'].map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={filters.review_status} onChange={e => setFilters(f => ({ ...f, review_status: e.target.value }))} style={inputStyle}>
          <option value="">Review…</option>
          {['pending', 'needs_review', 'reviewed', 'changes_requested', 'closed'].map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={filters.risk_level} onChange={e => setFilters(f => ({ ...f, risk_level: e.target.value }))} style={inputStyle}>
          <option value="">Risk…</option>
          {['low', 'medium', 'high', 'critical'].map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {msg && <div style={{ padding: '8px 12px', marginBottom: 12, borderRadius: 6, background: 'rgba(var(--accent-rgb),0.12)', border: '1px solid rgba(var(--accent-rgb),0.3)' }}>{msg}</div>}

      {isLoading ? <div>Loading…</div> : (
        <div style={{ display: 'grid', gridTemplateColumns: active ? '1fr 360px' : '1fr', gap: 18 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr>
                {['Student', 'Week', 'Status', 'Review', 'Risk', ''].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '8px 10px', borderBottom: '1px solid var(--border)', color: 'var(--text-dim)', fontSize: 12 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(reports || []).map(r => (
                <tr key={r.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '8px 10px' }}>{nameOf(r.student_id)}</td>
                  <td style={{ padding: '8px 10px' }}>{r.week_start}</td>
                  <td style={{ padding: '8px 10px' }}>{r.status}</td>
                  <td style={{ padding: '8px 10px' }}>{r.review_status}</td>
                  <td style={{ padding: '8px 10px' }}>{r.risk_override || r.risk_level}</td>
                  <td style={{ padding: '8px 10px' }}>
                    <button onClick={() => { setActive(r); setFeedback(r.feedback || '') }} style={btnGhost}>Review</button>
                  </td>
                </tr>
              ))}
              {!reports?.length && (
                <tr><td colSpan={6} style={{ padding: 16, color: 'var(--text-2)' }}>No reports match these filters.</td></tr>
              )}
            </tbody>
          </table>

          {active && (
            <aside style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 14, background: 'var(--surface-panel)', height: 'fit-content' }}>
              <h3 style={{ margin: '0 0 8px', color: 'var(--text-heading)' }}>{nameOf(active.student_id)}</h3>
              <div style={{ fontSize: 13, color: 'var(--text-2)', marginBottom: 10 }}>
                {active.week_start} · {active.items.length} item updates
              </div>
              {active.accomplished && <p style={{ fontSize: 13 }}><strong>Accomplished:</strong> {active.accomplished}</p>}
              {active.next_focus && <p style={{ fontSize: 13 }}><strong>Next:</strong> {active.next_focus}</p>}
              {active.support_requested && <p style={{ fontSize: 13 }}><strong>Support:</strong> {active.support_requested}</p>}

              <div style={{ display: 'grid', gap: 8, marginTop: 12 }}>
                <select
                  value={active.review_status}
                  onChange={e => setActive(a => a ? { ...a, review_status: e.target.value } : a)}
                  style={inputStyle}
                >
                  {['pending', 'needs_review', 'reviewed', 'changes_requested', 'closed'].map(s => <option key={s} value={s}>{s}</option>)}
                </select>
                <select
                  value={active.risk_override || ''}
                  onChange={e => setActive(a => a ? { ...a, risk_override: e.target.value || null } : a)}
                  style={inputStyle}
                >
                  <option value="">Risk override…</option>
                  {['low', 'medium', 'high', 'critical'].map(s => <option key={s} value={s}>{s}</option>)}
                </select>
                <textarea placeholder="Feedback" value={feedback} onChange={e => setFeedback(e.target.value)} style={{ ...inputStyle, minHeight: 80 }} />
                <button onClick={saveReview} style={btnPrimary}>Save review</button>
                <button onClick={() => setActive(null)} style={btnGhost}>Close</button>
              </div>
            </aside>
          )}
        </div>
      )}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  padding: '8px 10px', fontSize: 14, fontFamily: 'var(--font-mono)',
  background: 'var(--surface-input)', border: '1px solid var(--border)',
  borderRadius: 5, color: 'var(--text)', boxSizing: 'border-box',
}

const btnPrimary: React.CSSProperties = {
  padding: '8px 14px', cursor: 'pointer', fontSize: 14, fontWeight: 700,
  background: 'var(--accent)', border: 'none', borderRadius: 6, color: '#fff',
}

const btnGhost: React.CSSProperties = {
  padding: '6px 10px', cursor: 'pointer', fontSize: 13,
  background: 'transparent', border: '1px solid var(--border)',
  borderRadius: 5, color: 'var(--text-2)',
}
