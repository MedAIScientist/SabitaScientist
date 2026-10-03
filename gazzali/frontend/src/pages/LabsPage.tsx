import React, { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, Lab } from '../api'
import { useAuth } from '../auth'

export function LabsPage() {
  const { token, role, isAdmin, username } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const isStudent = role === 'student' && !isAdmin
  const [labs, setLabs] = useState<Lab[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(params.get('new') === '1')
  const [newName, setNewName] = useState('')
  const [newDept, setNewDept] = useState('')
  const [newUni, setNewUni] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  useEffect(() => { load() }, [token])

  async function load() {
    if (!token) return
    setLoading(true)
    try {
      setLabs(await api.listLabs())
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load labs')
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreateError(null)
    setCreating(true)
    try {
      await api.createLab(newName, newDept || undefined, newUni || undefined)
      setNewName(''); setNewDept(''); setNewUni('')
      setShowForm(false)
      await load()
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : 'Create failed')
    } finally {
      setCreating(false)
    }
  }

  const inputStyle: React.CSSProperties = {
    padding: '9px 12px',
    background: 'var(--surface-input)',
    border: '1px solid var(--border)',
    borderRadius: 7, color: 'var(--text)',
    fontSize: 17, outline: 'none',
    width: '100%',
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <div className="page-header" style={{ maxWidth: 1100, margin: '0 auto', padding: '28px 32px 0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <h1 className="page-title">Labs</h1>
        </div>

        {!isStudent && <button
          onClick={() => { setShowForm(f => !f); setCreateError(null) }} className="btn btn-primary">+ New lab</button>}
      </div>

      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0 32px 40px' }}>
        {isStudent && (
          <p style={{ color: 'var(--text-2)', margin: '0 0 18px' }}>
            Ask to join your professor's lab; once the PI approves, they supervise your progress.
          </p>
        )}
        {showForm && !isStudent && (
          <form onSubmit={handleCreate} style={{
            background: 'var(--surface-card)',
            border: '1px solid rgba(var(--accent-rgb),0.2)',
            borderRadius: 10, padding: '24px 24px 20px',
            marginBottom: 28,
          }}>
            <div style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)', marginBottom: 20 }}>
              Create lab
            </div>
            {createError && (
              <div style={{
                padding: '8px 12px', marginBottom: 16,
                background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.2)',
                borderRadius: 6, color: '#f43f5e', fontSize: 16,
              }}>{createError}</div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.04em', fontFamily: 'var(--font-mono)' }}>Name *</label>
                <input value={newName} onChange={e => setNewName(e.target.value)} required placeholder="My Lab" style={inputStyle} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.04em', fontFamily: 'var(--font-mono)' }}>Department</label>
                <input value={newDept} onChange={e => setNewDept(e.target.value)} placeholder="Computer Science" style={inputStyle} />
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 20 }}>
              <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.04em', fontFamily: 'var(--font-mono)' }}>University</label>
              <input value={newUni} onChange={e => setNewUni(e.target.value)} placeholder="University of ..." style={inputStyle} />
            </div>
            <button type="submit" disabled={creating} style={{
              padding: '9px 24px', cursor: creating ? 'default' : 'pointer',
              background: creating ? 'rgba(var(--accent-rgb),0.07)' : 'rgba(var(--accent-rgb),0.12)',
              border: '1px solid rgba(var(--accent-rgb),0.28)',
              borderRadius: 7, color: 'var(--accent)',
              fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
            }}>{creating ? 'Creating…' : 'Create'}</button>
          </form>
        )}

        {loading ? (
          <div style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 16, padding: '40px 0', textAlign: 'center' }}>Loading…</div>
        ) : error ? (
          <div style={{ color: '#f43f5e', fontSize: 16 }}>{error}</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', marginBottom: 4 }}>
              {labs.length} lab{labs.length !== 1 ? 's' : ''}
            </div>
            {labs.map(lab => (
              <div key={lab.id}
                onClick={() => navigate(`/labs/${lab.id}`)}
                style={{
                  background: 'var(--surface-card)',
                  border: '1px solid var(--border)',
                  borderRadius: 10, padding: '16px 20px',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  cursor: 'pointer', transition: 'border-color 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(var(--accent-rgb),0.2)' }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  <div style={{
                    width: 42, height: 42, borderRadius: 10,
                    background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 16, fontWeight: 700, color: '#fff',
                    fontFamily: 'var(--font-mono)', flexShrink: 0,
                  }}>
                    {lab.name[0].toUpperCase()}
                  </div>
                  <div>
                    <div style={{ fontSize: 20, fontWeight: 500, color: 'var(--text-heading)' }}>
                      {lab.name}
                    </div>
                    <div style={{ fontSize: 15, color: 'var(--text-dim)', marginTop: 2 }}>
                      {lab.department || ''}{lab.department && lab.university ? ' · ' : ''}{lab.university || ''}
                      <span style={{ marginLeft: 12, color: 'var(--text-3)' }}>
                        {lab.member_count} member{lab.member_count !== 1 ? 's' : ''}
                      </span>
                    </div>
                  </div>
                </div>
                {isStudent && !lab.members.some(m => m.username === username)
                  ? <JoinButton lab={lab} />
                  : <span style={{ color: 'var(--text-3)', fontSize: 17 }}>→</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function JoinButton({ lab }: { lab: Lab }) {
  const qc = useQueryClient()
  const { data: mine = [] } = useQuery({ queryKey: ['lab-join-mine'], queryFn: api.myLabJoinRequests })
  const join = useMutation({
    mutationFn: (labRole: 'phd' | 'ms') => api.requestToJoinLab(lab.id, labRole),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lab-join-mine'] }),
  })
  const last = mine.find(r => r.lab_id === lab.id)
  if (last?.status === 'pending') return <span className="chip">Request sent</span>
  return (
    <span onClick={e => e.stopPropagation()} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      {last?.status === 'declined' && <span className="chip">Declined</span>}
      {join.isError && <span style={{ color: '#f43f5e', fontSize: 14 }}>{(join.error as Error).message}</span>}
      <button className="btn" disabled={join.isPending} onClick={() => join.mutate('phd')}>Join as PhD</button>
      <button className="btn" disabled={join.isPending} onClick={() => join.mutate('ms')}>Join as MS</button>
    </span>
  )
}
