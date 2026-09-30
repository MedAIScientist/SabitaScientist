import React, { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, GRANT_MILESTONE_KINDS } from '../../api'

const KIND_COLORS: Record<string, string> = {
  milestone: '#ff8015',
  report: '#6366f1',
  deliverable: '#10b981',
}

const inputStyle: React.CSSProperties = {
  padding: '8px 10px', background: 'var(--surface-input)',
  border: '1px solid var(--border)', borderRadius: 6,
  color: 'var(--text)', fontSize: 16, outline: 'none', width: '100%',
}

const smallBtn: React.CSSProperties = {
  cursor: 'pointer', padding: '5px 10px', borderRadius: 6,
  background: 'transparent', border: '1px solid var(--border)',
  color: 'var(--text-muted)', fontSize: 14,
  fontFamily: 'var(--font-mono)', fontWeight: 700,
}

const labelStyle: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 5,
  fontSize: 14, fontWeight: 700, color: 'var(--text-dim)',
  fontFamily: 'var(--font-mono)', letterSpacing: '0.04em',
}

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

export function GrantMilestonesTab({ grantId, canEdit }: { grantId: string; canEdit: boolean }) {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [title, setTitle] = useState('')
  const [kind, setKind] = useState('milestone')
  const [dueDate, setDueDate] = useState('')
  const [ownerId, setOwnerId] = useState<string | null>(null)
  const [notes, setNotes] = useState('')
  const [showCompleted, setShowCompleted] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const { data: milestones = [], isLoading } = useQuery({
    queryKey: ['grant-milestones', grantId],
    queryFn: () => api.listGrantMilestones(grantId),
  })
  const { data: team = [] } = useQuery({
    queryKey: ['grant-members', grantId],
    queryFn: () => api.listGrantMembers(grantId),
  })

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['grant-milestones', grantId] })
    qc.invalidateQueries({ queryKey: ['grant-stats'] })
  }

  const create = useMutation({
    mutationFn: () => api.createGrantMilestone(grantId, {
      title,
      kind,
      due_date: dueDate || null,
      owner_id: ownerId,
      notes: notes || null,
    }),
    onSuccess: () => {
      refresh(); setShowForm(false); setTitle(''); setDueDate('')
      setOwnerId(null); setNotes(''); setError(null)
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : 'Could not add the item'),
  })

  const toggle = useMutation({
    mutationFn: ({ id, completed }: { id: string; completed: boolean }) =>
      api.updateGrantMilestone(grantId, id, { completed }),
    onSuccess: refresh,
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteGrantMilestone(grantId, id),
    onSuccess: refresh,
  })

  const visible = showCompleted ? milestones : milestones.filter(m => !m.completed_at)
  const overdue = milestones.filter(
    m => !m.completed_at && m.due_date && m.due_date.slice(0, 10) < today()
  ).length

  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: 14, gap: 12, flexWrap: 'wrap',
      }}>
        <div style={{ fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
          {milestones.length} item{milestones.length !== 1 ? 's' : ''}
          {overdue > 0 && <span style={{ color: '#f43f5e' }}> · {overdue} OVERDUE</span>}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={smallBtn} onClick={() => setShowCompleted(v => !v)}>
            {showCompleted ? 'HIDE COMPLETED' : 'SHOW COMPLETED'}
          </button>
          {canEdit && (
            <button
              onClick={() => setShowForm(v => !v)}
              style={{ ...smallBtn, padding: '7px 14px', borderColor: 'rgba(var(--accent-rgb),0.3)', color: 'var(--accent)' }}
            >+ Add</button>
          )}
        </div>
      </div>

      {error && (
        <div style={{
          padding: '8px 12px', marginBottom: 12, background: 'rgba(244,63,94,0.08)',
          border: '1px solid rgba(244,63,94,0.2)', borderRadius: 6, color: '#f43f5e',
          fontSize: 15, fontFamily: 'var(--font-mono)',
        }}>{error}</div>
      )}

      {canEdit && showForm && (
        <div style={{
          background: 'var(--surface-card)', border: '1px solid rgba(var(--accent-rgb),0.2)',
          borderRadius: 10, padding: 16, marginBottom: 14,
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 10 }}>
            <label style={{ ...labelStyle, gridColumn: '1 / -1' }}>
              Title
              <input
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder="e.g. Interim report to funder"
                style={inputStyle}
              />
            </label>
            <label style={labelStyle}>
              Type
              <select value={kind} onChange={e => setKind(e.target.value)} style={inputStyle}>
                {GRANT_MILESTONE_KINDS.map(k => <option key={k} value={k}>{k}</option>)}
              </select>
            </label>
            <label style={labelStyle}>
              Due date
              <input
                type="date"
                value={dueDate}
                onChange={e => setDueDate(e.target.value)}
                style={inputStyle}
              />
            </label>
            <label style={labelStyle}>
              Owner
              <select
                value={ownerId ?? ''}
                onChange={e => setOwnerId(e.target.value || null)}
                style={inputStyle}
              >
                <option value="">— none —</option>
                {team.map(m => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.username ?? m.user_id.slice(0, 8)}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ ...labelStyle, gridColumn: '1 / -1' }}>
              Notes
              <input
                value={notes}
                onChange={e => setNotes(e.target.value)}
                placeholder="optional"
                style={inputStyle}
              />
            </label>
          </div>
          {team.length === 0 && (
            <div style={{
              fontSize: 14, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
              marginTop: 8,
            }}>
              TIP: add people on the TEAM tab to assign an owner.
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button
              onClick={() => create.mutate()}
              disabled={!title.trim() || create.isPending}
              style={{
                cursor: !title.trim() ? 'default' : 'pointer', padding: '9px 20px',
                borderRadius: 7, border: 'none',
                background: !title.trim() || create.isPending ? 'rgba(var(--accent-rgb),0.4)' : '#ff8015',
                color: '#06091a', fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
              }}
            >{create.isPending ? 'SAVING…' : 'ADD'}</button>
            <button style={{ ...smallBtn, padding: '9px 14px' }} onClick={() => setShowForm(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <Muted>Loading…</Muted>
      ) : visible.length === 0 ? (
        <Muted>{milestones.length === 0 ? 'No milestones yet.' : 'Nothing to show.'}</Muted>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {visible.map(m => {
            const done = Boolean(m.completed_at)
            const late = !done && m.due_date && m.due_date.slice(0, 10) < today()
            const owner = team.find(t => t.user_id === m.owner_id)
            return (
              <div key={m.id} style={{
                display: 'flex', alignItems: 'flex-start', gap: 12,
                background: 'var(--surface-card)', border: '1px solid var(--border)',
                borderLeft: `3px solid ${late ? '#f43f5e' : KIND_COLORS[m.kind] ?? '#6b7280'}`,
                borderRadius: '0 10px 10px 0', padding: '14px 18px',
                opacity: done ? 0.6 : 1,
              }}>
                <input
                  type="checkbox"
                  checked={done}
                  disabled={!canEdit}
                  onChange={e => toggle.mutate({ id: m.id, completed: e.target.checked })}
                  style={{ marginTop: 4, cursor: canEdit ? 'pointer' : 'default', width: 16, height: 16 }}
                />
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontSize: 16, color: 'var(--text-heading)',
                    textDecoration: done ? 'line-through' : 'none',
                  }}>{m.title}</div>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 10, marginTop: 5,
                    flexWrap: 'wrap', fontSize: 14, fontFamily: 'var(--font-mono)',
                  }}>
                    <span style={{
                      color: KIND_COLORS[m.kind] ?? '#6b7280',
                      background: `${KIND_COLORS[m.kind] ?? '#6b7280'}14`,
                      border: `1px solid ${KIND_COLORS[m.kind] ?? '#6b7280'}30`,
                      borderRadius: 4, padding: '1px 7px', letterSpacing: '0.04em',
                    }}>{m.kind.toUpperCase()}</span>
                    <span style={{ color: late ? '#f43f5e' : 'var(--text-dim)' }}>
                      {m.due_date ? `DUE ${m.due_date.slice(0, 10)}` : 'NO DUE DATE'}
                      {late ? ' · OVERDUE' : ''}
                    </span>
                    {owner && <span style={{ color: 'var(--text-dim)' }}>{owner.username}</span>}
                    {done && (
                      <span style={{ color: '#10b981' }}>
                        DONE {m.completed_at?.slice(0, 10)}
                      </span>
                    )}
                  </div>
                  {m.notes && (
                    <div style={{ fontSize: 15, color: 'var(--text-2)', marginTop: 6 }}>{m.notes}</div>
                  )}
                </div>
                {canEdit && (
                  <button
                    style={{ ...smallBtn, borderColor: 'rgba(244,63,94,0.3)', color: '#f43f5e' }}
                    onClick={() => {
                      if (window.confirm(`Delete "${m.title}"?`)) remove.mutate(m.id)
                    }}
                  >Delete</button>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function Muted({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      padding: '20px 0', color: 'var(--text-dim)',
      fontFamily: 'var(--font-mono)', fontSize: 15,
    }}>{children}</div>
  )
}
