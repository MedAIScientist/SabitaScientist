import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, Lab } from '../api'
import { useAuth } from '../auth'

export function LabsPage() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const [labs, setLabs] = useState<Lab[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
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
    fontSize: 22, outline: 'none',
    width: '100%',
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <div style={{
        padding: '0 28px', height: 54,
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'var(--surface-header)', backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            onClick={() => navigate(-1)}
            style={{
              cursor: 'pointer', background: 'var(--surface-input)',
              border: '1px solid var(--border)', borderRadius: 6,
              color: 'var(--text-muted)', padding: '3px 9px', fontSize: 22, lineHeight: 1,
            }}
          >←</button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <img src="/sabita.jpg" alt="SABITA" style={{ height: 26, borderRadius: 4 }} />
            <span style={{ color: 'var(--text-dim)', fontSize: 20, fontFamily: 'var(--font-mono)' }}>/</span>
            <span style={{ color: '#ff8015', fontSize: 21, fontFamily: 'var(--font-mono)' }}>labs</span>
          </div>
        </div>

        <button
          onClick={() => { setShowForm(f => !f); setCreateError(null) }}
          style={{
            cursor: 'pointer', padding: '7px 16px',
            background: showForm ? 'rgba(255,128,21,0.18)' : 'rgba(255,128,21,0.1)',
            border: '1px solid rgba(255,128,21,0.3)',
            borderRadius: 7, color: '#ff8015',
            fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)',
            letterSpacing: '0.08em',
          }}
        >+ NEW LAB</button>
      </div>

      <div style={{ maxWidth: 680, margin: '0 auto', padding: '32px 28px' }}>
        {showForm && (
          <form onSubmit={handleCreate} style={{
            background: 'var(--surface-card)',
            border: '1px solid rgba(255,128,21,0.2)',
            borderRadius: 10, padding: '24px 24px 20px',
            marginBottom: 28,
          }}>
            <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)', marginBottom: 20 }}>
              CREATE LAB
            </div>
            {createError && (
              <div style={{
                padding: '8px 12px', marginBottom: 16,
                background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.2)',
                borderRadius: 6, color: '#f43f5e', fontSize: 19,
              }}>{createError}</div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.1em', fontFamily: 'var(--font-mono)' }}>NAME *</label>
                <input value={newName} onChange={e => setNewName(e.target.value)} required placeholder="My Lab" style={inputStyle} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.1em', fontFamily: 'var(--font-mono)' }}>DEPARTMENT</label>
                <input value={newDept} onChange={e => setNewDept(e.target.value)} placeholder="Computer Science" style={inputStyle} />
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 20 }}>
              <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.1em', fontFamily: 'var(--font-mono)' }}>UNIVERSITY</label>
              <input value={newUni} onChange={e => setNewUni(e.target.value)} placeholder="University of ..." style={inputStyle} />
            </div>
            <button type="submit" disabled={creating} style={{
              padding: '9px 24px', cursor: creating ? 'default' : 'pointer',
              background: creating ? 'rgba(255,128,21,0.07)' : 'rgba(255,128,21,0.12)',
              border: '1px solid rgba(255,128,21,0.28)',
              borderRadius: 7, color: '#ff8015',
              fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)',
            }}>{creating ? 'CREATING…' : 'CREATE'}</button>
          </form>
        )}

        {loading ? (
          <div style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 19, padding: '40px 0', textAlign: 'center' }}>LOADING…</div>
        ) : error ? (
          <div style={{ color: '#f43f5e', fontSize: 19 }}>{error}</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', marginBottom: 4 }}>
              {labs.length} LAB{labs.length !== 1 ? 'S' : ''}
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
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(255,128,21,0.2)' }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  <div style={{
                    width: 42, height: 42, borderRadius: 10,
                    background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 20, fontWeight: 700, color: '#fff',
                    fontFamily: 'var(--font-mono)', flexShrink: 0,
                  }}>
                    {lab.name[0].toUpperCase()}
                  </div>
                  <div>
                    <div style={{ fontSize: 24, fontWeight: 500, color: 'var(--text-heading)' }}>
                      {lab.name}
                    </div>
                    <div style={{ fontSize: 18, color: 'var(--text-dim)', marginTop: 2 }}>
                      {lab.department || ''}{lab.department && lab.university ? ' · ' : ''}{lab.university || ''}
                      <span style={{ marginLeft: 12, color: 'var(--text-3)' }}>
                        {lab.members.length} member{lab.members.length !== 1 ? 's' : ''}
                      </span>
                    </div>
                  </div>
                </div>
                <span style={{ color: 'var(--text-3)', fontSize: 22 }}>→</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
