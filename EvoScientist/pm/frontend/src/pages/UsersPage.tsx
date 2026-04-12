import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, UserRecord } from '../api'
import { useAuth } from '../auth'

export function UsersPage() {
  const { isAdmin } = useAuth()
  const navigate = useNavigate()

  const [users, setUsers] = useState<UserRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Create form state
  const [showForm, setShowForm] = useState(false)
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newEmail, setNewEmail] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  // Delete confirm state
  const [deleteTarget, setDeleteTarget] = useState<UserRecord | null>(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    if (!isAdmin) { navigate('/projects', { replace: true }); return }
    load()
  }, [isAdmin])

  async function load() {
    setLoading(true)
    try {
      setUsers(await api.listUsers())
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreateError(null)
    setCreating(true)
    try {
      await api.createUser(newUsername, newPassword, newEmail || undefined)
      setNewUsername(''); setNewPassword(''); setNewEmail('')
      setShowForm(false)
      await load()
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : 'Create failed')
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await api.deleteUser(deleteTarget.id)
      setDeleteTarget(null)
      await load()
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Delete failed')
    } finally {
      setDeleting(false)
    }
  }

  const labelStyle: React.CSSProperties = {
    fontSize: 15, fontWeight: 700, color: 'var(--text-dim)',
    letterSpacing: '0.1em', fontFamily: 'var(--font-mono)',
  }
  const inputStyle: React.CSSProperties = {
    padding: '9px 12px',
    background: 'var(--surface-input)',
    border: '1px solid var(--border)',
    borderRadius: 7, color: 'var(--text)',
    fontSize: 22, outline: 'none',
    transition: 'border-color 0.14s',
    width: '100%',
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>

      {/* Header */}
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
              transition: 'color 0.15s, border-color 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = '#ff8015'; e.currentTarget.style.borderColor = 'rgba(255,128,21,0.3)' }}
            onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.borderColor = 'var(--border)' }}
          >←</button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <img src="/sabita.jpg" alt="SABITA" style={{ height: 26, borderRadius: 4 }} />
            <span style={{ color: 'var(--text-dim)', fontSize: 20, fontFamily: 'var(--font-mono)' }}>/</span>
            <span style={{ color: '#ff8015', fontSize: 21, fontFamily: 'var(--font-mono)' }}>users</span>
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
            letterSpacing: '0.08em', transition: 'background 0.14s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.22)' }}
          onMouseLeave={e => { e.currentTarget.style.background = showForm ? 'rgba(255,128,21,0.18)' : 'rgba(255,128,21,0.1)' }}
        >+ ADD USER</button>
      </div>

      <div style={{ maxWidth: 680, margin: '0 auto', padding: '32px 28px' }}>

        {/* Create form */}
        {showForm && (
          <form onSubmit={handleCreate} style={{
            background: 'var(--surface-card)',
            border: '1px solid rgba(255,128,21,0.2)',
            borderRadius: 10, padding: '24px 24px 20px',
            marginBottom: 28,
            animation: 'fadeInUp 0.2s ease',
          }}>
            <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)', marginBottom: 20, letterSpacing: '0.04em' }}>
              NEW USER
            </div>

            {createError && (
              <div style={{
                padding: '8px 12px', marginBottom: 16,
                background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.2)',
                borderRadius: 6, color: '#f43f5e', fontSize: 19, fontFamily: 'var(--font-mono)',
              }}>{createError}</div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={labelStyle}>USERNAME *</label>
                <input
                  value={newUsername} onChange={e => setNewUsername(e.target.value)}
                  required placeholder="username"
                  style={inputStyle}
                  onFocus={e => { e.currentTarget.style.borderColor = 'rgba(255,128,21,0.35)' }}
                  onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={labelStyle}>PASSWORD *</label>
                <input
                  type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)}
                  required placeholder="••••••••"
                  style={inputStyle}
                  onFocus={e => { e.currentTarget.style.borderColor = 'rgba(255,128,21,0.35)' }}
                  onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 20 }}>
              <label style={labelStyle}>EMAIL <span style={{ color: 'var(--text-3)', fontWeight: 400 }}>(optional)</span></label>
              <input
                type="email" value={newEmail} onChange={e => setNewEmail(e.target.value)}
                placeholder="user@example.com"
                style={inputStyle}
                onFocus={e => { e.currentTarget.style.borderColor = 'rgba(255,128,21,0.35)' }}
                onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
              />
            </div>

            <div style={{ display: 'flex', gap: 10 }}>
              <button
                type="submit" disabled={creating}
                style={{
                  padding: '9px 24px', cursor: creating ? 'default' : 'pointer',
                  background: creating ? 'rgba(255,128,21,0.07)' : 'rgba(255,128,21,0.12)',
                  border: '1px solid rgba(255,128,21,0.28)',
                  borderRadius: 7, color: '#ff8015',
                  fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)',
                  letterSpacing: '0.08em', transition: 'background 0.14s',
                }}
                onMouseEnter={e => { if (!creating) e.currentTarget.style.background = 'rgba(255,128,21,0.22)' }}
                onMouseLeave={e => { e.currentTarget.style.background = creating ? 'rgba(255,128,21,0.07)' : 'rgba(255,128,21,0.12)' }}
              >{creating ? 'CREATING…' : 'CREATE'}</button>
              <button
                type="button" onClick={() => { setShowForm(false); setCreateError(null) }}
                style={{
                  padding: '9px 18px', cursor: 'pointer',
                  background: 'transparent', border: '1px solid var(--border)',
                  borderRadius: 7, color: 'var(--text-muted)',
                  fontSize: 18, fontFamily: 'var(--font-mono)', transition: 'border-color 0.14s',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--text-muted)' }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
              >CANCEL</button>
            </div>
          </form>
        )}

        {/* User list */}
        {loading ? (
          <div style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 19, padding: '40px 0', textAlign: 'center' }}>
            LOADING…
          </div>
        ) : error ? (
          <div style={{ color: '#f43f5e', fontFamily: 'var(--font-mono)', fontSize: 19 }}>{error}</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', marginBottom: 4 }}>
              {users.length} USER{users.length !== 1 ? 'S' : ''}
            </div>
            {users.map(u => (
              <div key={u.id} style={{
                background: 'var(--surface-card)',
                border: '1px solid var(--border)',
                borderRadius: 10, padding: '16px 20px',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                transition: 'border-color 0.15s',
              }}
                onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(255,128,21,0.2)' }}
                onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border)' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  {/* Avatar */}
                  <div style={{
                    width: 42, height: 42, borderRadius: '50%',
                    background: 'linear-gradient(135deg, #ff8015, #8b5cf6)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 27, fontWeight: 700, color: '#fff',
                    fontFamily: 'var(--font-mono)', flexShrink: 0,
                  }}>
                    {u.username[0].toUpperCase()}
                  </div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 24, fontWeight: 500, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)' }}>
                        {u.username}
                      </span>
                      {u.is_admin && (
                        <span style={{
                          fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)',
                          color: '#ff8015', background: 'rgba(255,128,21,0.1)',
                          border: '1px solid rgba(255,128,21,0.25)',
                          borderRadius: 4, padding: '1px 7px', letterSpacing: '0.06em',
                        }}>ADMIN</span>
                      )}
                    </div>
                    <div style={{ fontSize: 18, color: 'var(--text-dim)', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
                      {u.email ?? <span style={{ color: 'var(--text-3)' }}>no email</span>}
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => setDeleteTarget(u)}
                  title="Delete user"
                  style={{
                    cursor: 'pointer', padding: '6px 14px',
                    background: 'rgba(244,63,94,0.06)',
                    border: '1px solid rgba(244,63,94,0.15)',
                    borderRadius: 6, color: '#f43f5e',
                    fontSize: 18, fontFamily: 'var(--font-mono)',
                    transition: 'background 0.14s, border-color 0.14s',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'rgba(244,63,94,0.14)'; e.currentTarget.style.borderColor = 'rgba(244,63,94,0.3)' }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'rgba(244,63,94,0.06)'; e.currentTarget.style.borderColor = 'rgba(244,63,94,0.15)' }}
                >DELETE</button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delete confirmation modal */}
      {deleteTarget && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 50,
          background: 'var(--overlay-bg)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={() => !deleting && setDeleteTarget(null)}>
          <div
            onClick={e => e.stopPropagation()}
            style={{
              background: 'var(--surface-panel)',
              border: '1px solid var(--border)',
              borderRadius: 12, padding: '28px 32px',
              width: 360, animation: 'fadeInUp 0.2s ease',
            }}
          >
            <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)', marginBottom: 10 }}>
              DELETE USER
            </div>
            <div style={{ fontSize: 21, color: 'var(--text-2)', marginBottom: 24 }}>
              Delete <strong style={{ color: 'var(--text-heading)' }}>{deleteTarget.username}</strong>? This cannot be undone.
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={handleDelete} disabled={deleting}
                style={{
                  flex: 1, padding: '10px 0', cursor: deleting ? 'default' : 'pointer',
                  background: deleting ? 'rgba(244,63,94,0.06)' : 'rgba(244,63,94,0.1)',
                  border: '1px solid rgba(244,63,94,0.25)',
                  borderRadius: 7, color: '#f43f5e',
                  fontSize: 19, fontWeight: 700, fontFamily: 'var(--font-mono)',
                  transition: 'background 0.14s',
                }}
                onMouseEnter={e => { if (!deleting) e.currentTarget.style.background = 'rgba(244,63,94,0.2)' }}
                onMouseLeave={e => { e.currentTarget.style.background = deleting ? 'rgba(244,63,94,0.06)' : 'rgba(244,63,94,0.1)' }}
              >{deleting ? 'DELETING…' : 'DELETE'}</button>
              <button
                onClick={() => setDeleteTarget(null)} disabled={deleting}
                style={{
                  flex: 1, padding: '10px 0', cursor: 'pointer',
                  background: 'transparent', border: '1px solid var(--border)',
                  borderRadius: 7, color: 'var(--text-muted)',
                  fontSize: 19, fontFamily: 'var(--font-mono)', transition: 'border-color 0.14s',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--text-muted)' }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
              >CANCEL</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
