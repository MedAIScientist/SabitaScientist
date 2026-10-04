import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { supervisionApi, api } from '../api'
import { useAuth } from '../auth'

const KINDS = ['all', 'publication', 'experiment', 'grant', 'patent']

/** Unified research pipeline: papers, patents, experiments, grants in one list. */
export function ResearchItemsPage() {
  const { role, isAdmin } = useAuth()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [kind, setKind] = useState('all')
  const [studentId, setStudentId] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [draftOpen, setDraftOpen] = useState(false)
  const [draftTitle, setDraftTitle] = useState('')
  const [msg, setMsg] = useState<string | null>(null)

  const isStudent = role === 'student' && !isAdmin
  const { data: users } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.listUsers(),
    enabled: !isStudent,
  })

  const { data: items, isLoading } = useQuery({
    queryKey: ['research-items', kind, studentId],
    queryFn: () => supervisionApi.researchItems({
      kind: kind === 'all' ? undefined : kind,
      student_id: studentId || undefined,
    }),
  })

  const nameOf = (id: string) => users?.find(u => u.id === id)?.username || ''

  function toggle(id: string) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function createPaperFromSelection() {
    const expIds = (items || [])
      .filter(i => selected.has(`${i.kind}-${i.id}`) && i.kind === 'experiment')
      .map(i => i.id)
    if (!draftTitle.trim()) return setMsg('Give the paper a title first')
    try {
      const result = await supervisionApi.draftPaperFromItems({
        title: draftTitle,
        experiment_ids: expIds,
        venue_type: 'journal',
      })
      setMsg(`Paper created: ${result.title}`)
      setDraftOpen(false)
      setDraftTitle('')
      setSelected(new Set())
      await qc.invalidateQueries({ queryKey: ['research-items'] })
      navigate(`/publications/${result.publication_id}/studio`)
    } catch (e: any) {
      setMsg(e.message)
    }
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1100 }}>
      <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', color: 'var(--text-dim)' }}>Research pipeline</div>
      <h1 style={{ margin: '4px 0 6px', fontSize: 22, color: 'var(--text-heading)' }}>Research items</h1>
      <p style={{ color: 'var(--text-2)', margin: '0 0 18px', fontSize: 14 }}>
        One durable record for each paper, patent, experiment, grant, or other work.
      </p>

      {msg && (
        <div style={{ padding: '8px 12px', marginBottom: 12, borderRadius: 6, background: 'rgba(var(--accent-rgb),0.12)', border: '1px solid rgba(var(--accent-rgb),0.3)', fontSize: 13 }}>{msg}</div>
      )}

      {draftOpen && (
        <div style={{ border: '1px solid rgba(var(--accent-rgb),0.35)', background: 'rgba(var(--accent-rgb),0.06)', borderRadius: 10, padding: 16, marginBottom: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-heading)', marginBottom: 10 }}>New paper from research items</div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <input
              placeholder="Paper title"
              value={draftTitle}
              onChange={e => setDraftTitle(e.target.value)}
              style={{ ...inputStyle, flex: 1, minWidth: 240 }}
            />
            <button onClick={createPaperFromSelection} style={btnPrimary}>Create paper</button>
            <button onClick={() => setDraftOpen(false)} style={btnGhost}>Cancel</button>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 8 }}>
            Selected experiments will be pre-linked for scoped section drafting.
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <button
          onClick={() => setDraftOpen(true)}
          disabled={selected.size === 0}
          style={{
            ...btnPrimary,
            opacity: selected.size === 0 ? 0.5 : 1,
          }}
        >✍ Draft paper ({selected.size})</button>
        <select value={kind} onChange={e => setKind(e.target.value)} style={{ ...inputStyle, width: 180 }}>
          {KINDS.map(k => <option key={k} value={k}>{k === 'all' ? 'All types' : k}</option>)}
        </select>
        {!isStudent && (
          <select value={studentId} onChange={e => setStudentId(e.target.value)} style={{ ...inputStyle, width: 200 }}>
            <option value="">All owners…</option>
            {(users || []).filter(u => !u.username.startsWith('_')).map(u => (
              <option key={u.id} value={u.id}>{u.username}</option>
            ))}
          </select>
        )}
      </div>

      {isLoading ? <div style={{ color: 'var(--text-2)' }}>Loading…</div> : (
        <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr>
                {['', 'Type', 'Title', 'Status', 'Venue / Funder', 'Owner', 'Updated', ''].map(h => (
                  <th key={h} style={th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(items || []).map(item => (
                <tr key={`${item.kind}-${item.id}`} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={td}>
                    {(item.kind === 'experiment' || item.kind === 'publication') && (
                      <input
                        type="checkbox"
                        checked={selected.has(`${item.kind}-${item.id}`)}
                        onChange={() => toggle(`${item.kind}-${item.id}`)}
                        style={{ cursor: 'pointer' }}
                      />
                    )}
                  </td>
                  <td style={td}>
                    <span style={{
                      fontSize: 11, fontFamily: 'var(--font-mono)', padding: '2px 8px',
                      borderRadius: 999, background: 'var(--surface-input)', border: '1px solid var(--border)',
                      color: 'var(--text-2)', textTransform: 'uppercase',
                    }}>{item.kind}</span>
                  </td>
                  <td style={{ ...td, fontWeight: 600 }}>{item.title}</td>
                  <td style={td}>
                    <span style={{ color: item.status === 'blocked' || item.status === 'rejected' ? '#f43f5e' : 'var(--text-2)' }}>
                      {item.status}
                    </span>
                  </td>
                  <td style={{ ...td, color: 'var(--text-2)', fontSize: 13 }}>{item.venue || '—'}</td>
                  <td style={{ ...td, fontSize: 13 }}>{nameOf(item.owner_id) || '—'}</td>
                  <td style={{ ...td, fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-2)' }}>
                    {(item.updated_at || item.created_at || '').slice(0, 10)}
                  </td>
                  <td style={{ ...td, whiteSpace: 'nowrap' }}>
                    {item.kind === 'publication' ? (
                      <button onClick={() => navigate(`/publications/${item.id}/studio`)} style={btnPrimary}>Studio</button>
                    ) : (
                      <button onClick={() => navigate(item.link_path)} style={btnGhost}>Open</button>
                    )}
                  </td>
                </tr>
              ))}
              {!items?.length && (
                <tr>
                  <td colSpan={8} style={{ ...td, color: 'var(--text-2)', padding: 20 }}>
                    No research items yet. Create publications, experiments, or grants to see them here.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
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
const th: React.CSSProperties = {
  textAlign: 'left', padding: '10px 12px', borderBottom: '1px solid var(--border)',
  background: 'var(--surface-input)', color: 'var(--text-dim)', fontSize: 11,
  fontFamily: 'var(--font-mono)', letterSpacing: '0.04em',
}
const td: React.CSSProperties = { padding: '10px 12px' }
const btnGhost: React.CSSProperties = {
  padding: '5px 10px', cursor: 'pointer', fontSize: 12,
  background: 'transparent', border: '1px solid var(--border)',
  borderRadius: 5, color: 'var(--text-2)',
}
const btnPrimary: React.CSSProperties = {
  padding: '6px 12px', cursor: 'pointer', fontSize: 12, fontWeight: 700,
  background: 'var(--accent)', border: 'none', borderRadius: 6, color: '#fff',
}
