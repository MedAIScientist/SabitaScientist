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
  const [newRole, setNewRole] = useState('student')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [showBulk, setShowBulk] = useState(false)
  const [bulkCsv, setBulkCsv] = useState('')
  const [bulkMsg, setBulkMsg] = useState<string | null>(null)

  // Edit state
  const [editTarget, setEditTarget] = useState<UserRecord | null>(null)
  const [editUsername, setEditUsername] = useState('')
  const [editEmail, setEditEmail] = useState('')
  const [editAdmin, setEditAdmin] = useState(false)
  const [editRole, setEditRole] = useState('student')
  const [editing, setEditing] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)

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
      await api.createUser(newUsername, newPassword, newEmail || undefined, newRole)
      setNewUsername(''); setNewPassword(''); setNewEmail(''); setNewRole('student')
      setShowForm(false)
      await load()
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : 'Create failed')
    } finally {
      setCreating(false)
    }
  }

  async function handleBulkImport() {
    setBulkMsg(null)
    try {
      const rows = bulkCsv.trim().split(/\r?\n/).filter(Boolean).map(line => {
        const [username, password, email, role] = line.split(',').map(x => x.trim())
        return { username, password, email: email || undefined, role: role || 'student' }
      }).filter(r => r.username && r.password)
      if (!rows.length) { setBulkMsg('No valid rows found. Format: username,password,email,role'); return }
      const result = await api.bulkImportUsers(rows)
      setBulkMsg(`Created ${result.created} user(s).${result.errors.length ? ' Errors: ' + result.errors.join('; ') : ''}`)
      setBulkCsv('')
      await load()
    } catch (err: unknown) {
      setBulkMsg(err instanceof Error ? err.message : 'Import failed')
    }
  }

  function openEdit(u: UserRecord) {
    setEditTarget(u)
    setEditUsername(u.username)
    setEditEmail(u.email ?? '')
    setEditAdmin(u.is_admin)
    setEditRole(u.role || 'student')
    setEditError(null)
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault()
    if (!editTarget) return
    setEditing(true)
    setEditError(null)
    try {
      await api.updateUser(editTarget.id, {
        username: editUsername !== editTarget.username ? editUsername : undefined,
        email: editEmail !== (editTarget.email ?? '') ? editEmail || null : undefined,
        is_admin: editAdmin !== editTarget.is_admin ? editAdmin : undefined,
        role: editRole !== (editTarget.role || 'student') ? editRole : undefined,
      })
      setEditTarget(null)
      await load()
    } catch (err: unknown) {
      setEditError(err instanceof Error ? err.message : 'Update failed')
    } finally {
      setEditing(false)
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
    letterSpacing: '0.04em', fontFamily: 'var(--font-mono)',
  }
  const inputStyle: React.CSSProperties = {
    padding: '9px 12px',
    background: 'var(--surface-input)',
    border: '1px solid var(--border)',
    borderRadius: 7, color: 'var(--text)',
    fontSize: 17, outline: 'none',
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
          <h1 className="page-title" style={{ fontSize: 18 }}>People</h1>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={() => { setShowBulk(b => !b); setBulkMsg(null) }}
          style={{
            cursor: 'pointer', padding: '7px 14px',
            background: 'transparent', border: '1px solid var(--border)',
            borderRadius: 7, color: 'var(--text-muted)',
            fontSize: 16, fontFamily: 'var(--font-mono)',
          }}
        >Bulk import</button>
        <button
          onClick={() => { setShowForm(f => !f); setCreateError(null) }}
          style={{
            cursor: 'pointer', padding: '7px 16px',
            background: showForm ? 'rgba(var(--accent-rgb),0.18)' : 'rgba(var(--accent-rgb),0.1)',
            border: '1px solid rgba(var(--accent-rgb),0.3)',
            borderRadius: 7, color: 'var(--accent)',
            fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
            letterSpacing: '0.04em', transition: 'background 0.14s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(var(--accent-rgb),0.22)' }}
          onMouseLeave={e => { e.currentTarget.style.background = showForm ? 'rgba(var(--accent-rgb),0.18)' : 'rgba(var(--accent-rgb),0.1)' }}
        >+ Add user</button>
        </div>
      </div>

      {showBulk && (
        <div style={{
          background: 'var(--surface-card)', border: '1px solid rgba(var(--accent-rgb),0.2)',
          borderRadius: 10, padding: '20px 24px', marginBottom: 24,
        }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)', marginBottom: 10, letterSpacing: '0.04em' }}>
            Bulk import (CSV)
          </div>
          <p style={{ fontSize: 15, color: 'var(--text-2)', margin: '0 0 12px' }}>
            One user per line: <code>username,password,email,role</code> — role is student | professor | admin.
          </p>
          {bulkMsg && (
            <div style={{ padding: '8px 12px', marginBottom: 12, borderRadius: 6, background: 'rgba(var(--accent-rgb),0.1)', border: '1px solid rgba(var(--accent-rgb),0.25)', fontSize: 15 }}>{bulkMsg}</div>
          )}
          <textarea
            value={bulkCsv} onChange={e => setBulkCsv(e.target.value)}
            placeholder={'alice,Secret123,alice@uni.edu,student\nbob,Secret456,bob@uni.edu,professor'}
            style={{ width: '100%', minHeight: 120, padding: 12, fontFamily: 'var(--font-mono)', fontSize: 14, background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', boxSizing: 'border-box', marginBottom: 12 }}
          />
          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={handleBulkImport} style={{ padding: '8px 18px', cursor: 'pointer', background: 'rgba(var(--accent-rgb),0.12)', border: '1px solid rgba(var(--accent-rgb),0.28)', borderRadius: 7, color: 'var(--accent)', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>Import</button>
            <button onClick={() => setShowBulk(false)} style={{ padding: '8px 18px', cursor: 'pointer', background: 'transparent', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>Close</button>
          </div>
        </div>
      )}

      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 28px' }}>

        {/* Create form */}
        {showForm && (
          <form onSubmit={handleCreate} style={{
            background: 'var(--surface-card)',
            border: '1px solid rgba(var(--accent-rgb),0.2)',
            borderRadius: 10, padding: '24px 24px 20px',
            marginBottom: 28,
            animation: 'fadeInUp 0.2s ease',
          }}>
            <div style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)', marginBottom: 20, letterSpacing: '0.04em' }}>
              New user
            </div>

            {createError && (
              <div style={{
                padding: '8px 12px', marginBottom: 16,
                background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.2)',
                borderRadius: 6, color: '#f43f5e', fontSize: 16, fontFamily: 'var(--font-mono)',
              }}>{createError}</div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={labelStyle}>Username *</label>
                <input
                  value={newUsername} onChange={e => setNewUsername(e.target.value)}
                  required placeholder="username"
                  style={inputStyle}
                  onFocus={e => { e.currentTarget.style.borderColor = 'rgba(var(--accent-rgb),0.35)' }}
                  onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={labelStyle}>Password *</label>
                <input
                  type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)}
                  required placeholder="••••••••"
                  style={inputStyle}
                  onFocus={e => { e.currentTarget.style.borderColor = 'rgba(var(--accent-rgb),0.35)' }}
                  onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 20 }}>
              <label style={labelStyle}>Email <span style={{ color: 'var(--text-3)', fontWeight: 400 }}>(optional)</span></label>
              <input
                type="email" value={newEmail} onChange={e => setNewEmail(e.target.value)}
                placeholder="user@example.com"
                style={inputStyle}
                onFocus={e => { e.currentTarget.style.borderColor = 'rgba(var(--accent-rgb),0.35)' }}
                onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 20 }}>
              <label style={labelStyle}>Role</label>
              <select value={newRole} onChange={e => setNewRole(e.target.value)} style={inputStyle}>
                <option value="student">student</option>
                <option value="professor">professor</option>
                <option value="admin">admin</option>
              </select>
            </div>

            <div style={{ display: 'flex', gap: 10 }}>
              <button
                type="submit" disabled={creating}
                style={{
                  padding: '9px 24px', cursor: creating ? 'default' : 'pointer',
                  background: creating ? 'rgba(var(--accent-rgb),0.07)' : 'rgba(var(--accent-rgb),0.12)',
                  border: '1px solid rgba(var(--accent-rgb),0.28)',
                  borderRadius: 7, color: 'var(--accent)',
                  fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
                  letterSpacing: '0.04em', transition: 'background 0.14s',
                }}
                onMouseEnter={e => { if (!creating) e.currentTarget.style.background = 'rgba(var(--accent-rgb),0.22)' }}
                onMouseLeave={e => { e.currentTarget.style.background = creating ? 'rgba(var(--accent-rgb),0.07)' : 'rgba(var(--accent-rgb),0.12)' }}
              >{creating ? 'CREATING…' : 'CREATE'}</button>
              <button
                type="button" onClick={() => { setShowForm(false); setCreateError(null) }}
                style={{
                  padding: '9px 18px', cursor: 'pointer',
                  background: 'transparent', border: '1px solid var(--border)',
                  borderRadius: 7, color: 'var(--text-muted)',
                  fontSize: 15, fontFamily: 'var(--font-mono)', transition: 'border-color 0.14s',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--text-muted)' }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
              >Cancel</button>
            </div>
          </form>
        )}

        {/* User list */}
        {loading ? (
          <div style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 16, padding: '40px 0', textAlign: 'center' }}>
            Loading…
          </div>
        ) : error ? (
          <div style={{ color: '#f43f5e', fontFamily: 'var(--font-mono)', fontSize: 16 }}>{error}</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', marginBottom: 4 }}>
              {users.length} user{users.length !== 1 ? 's' : ''}
            </div>
            {users.map(u => (
              <div key={u.id} style={{
                background: 'var(--surface-card)',
                border: '1px solid var(--border)',
                borderRadius: 10, padding: '16px 20px',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                transition: 'border-color 0.15s',
              }}
                onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(var(--accent-rgb),0.2)' }}
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
                      <span style={{ fontSize: 20, fontWeight: 500, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)' }}>
                        {u.username}
                      </span>
                      <span style={{
                        fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)',
                        color: u.role === 'professor' ? 'var(--accent)' : 'var(--text-2)',
                        background: 'var(--surface-input)',
                        border: '1px solid var(--border)',
                        borderRadius: 4, padding: '1px 7px', letterSpacing: '0.04em',
                      }}>{(u.role || 'student').toUpperCase()}</span>
                      {u.is_admin && (
                        <span style={{
                          fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)',
                          color: 'var(--accent)', background: 'rgba(var(--accent-rgb),0.1)',
                          border: '1px solid rgba(var(--accent-rgb),0.25)',
                          borderRadius: 4, padding: '1px 7px', letterSpacing: '0.04em',
                        }}>Admin</span>
                      )}
                    </div>
                    <div style={{ fontSize: 15, color: 'var(--text-dim)', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
                      {u.email ?? <span style={{ color: 'var(--text-3)' }}>no email</span>}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 6 }}>
                <button
                  onClick={() => openEdit(u)}
                  title="Edit user"
                  style={{
                    cursor: 'pointer', padding: '6px 14px',
                    background: 'rgba(16,185,129,0.06)',
                    border: '1px solid rgba(16,185,129,0.15)',
                    borderRadius: 6, color: '#10b981',
                    fontSize: 15, fontFamily: 'var(--font-mono)',
                    transition: 'background 0.14s',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'rgba(16,185,129,0.14)' }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'rgba(16,185,129,0.06)' }}
                >Edit</button>
                <button
                  onClick={() => setDeleteTarget(u)}
                  title="Delete user"
                  style={{
                    cursor: 'pointer', padding: '6px 14px',
                    background: 'rgba(244,63,94,0.06)',
                    border: '1px solid rgba(244,63,94,0.15)',
                    borderRadius: 6, color: '#f43f5e',
                    fontSize: 15, fontFamily: 'var(--font-mono)',
                    transition: 'background 0.14s, border-color 0.14s',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'rgba(244,63,94,0.14)'; e.currentTarget.style.borderColor = 'rgba(244,63,94,0.3)' }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'rgba(244,63,94,0.06)'; e.currentTarget.style.borderColor = 'rgba(244,63,94,0.15)' }}
                >Delete</button>
              </div>
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
            <div style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)', marginBottom: 10 }}>
              Delete user
            </div>
            <div style={{ fontSize: 17, color: 'var(--text-2)', marginBottom: 24 }}>
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
                  fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
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
                  fontSize: 16, fontFamily: 'var(--font-mono)', transition: 'border-color 0.14s',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--text-muted)' }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
              >Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* Edit modal */}
      {editTarget && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 50,
          background: 'var(--overlay-bg)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={() => !editing && setEditTarget(null)}>
          <div onClick={e => e.stopPropagation()} style={{
            background: 'var(--surface-panel)', border: '1px solid var(--border)',
            borderRadius: 12, padding: '28px 32px', width: 400, animation: 'fadeInUp 0.2s ease',
          }}>
            <form onSubmit={handleEdit}>
              <div style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)', marginBottom: 20 }}>
                Edit user
              </div>

              {editError && (
                <div style={{ padding: '8px 12px', marginBottom: 16, background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.2)', borderRadius: 6, color: '#f43f5e', fontSize: 16, fontFamily: 'var(--font-mono)' }}>{editError}</div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
                <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.04em', fontFamily: 'var(--font-mono)' }}>Username</label>
                <input value={editUsername} onChange={e => setEditUsername(e.target.value)} required
                  style={{ padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 17, outline: 'none', width: '100%', boxSizing: 'border-box' }} />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
                <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.04em', fontFamily: 'var(--font-mono)' }}>Email</label>
                <input value={editEmail} onChange={e => setEditEmail(e.target.value)} type="email"
                  style={{ padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 17, outline: 'none', width: '100%', boxSizing: 'border-box' }} />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
                <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.04em', fontFamily: 'var(--font-mono)' }}>Role</label>
                <select value={editRole} onChange={e => setEditRole(e.target.value)}
                  style={{ padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 17, outline: 'none', width: '100%', boxSizing: 'border-box' }}>
                  <option value="student">student</option>
                  <option value="professor">professor</option>
                  <option value="admin">admin</option>
                </select>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
                <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.04em', fontFamily: 'var(--font-mono)' }}>Admin</label>
                <input type="checkbox" checked={editAdmin} onChange={e => setEditAdmin(e.target.checked)}
                  style={{ width: 20, height: 20, cursor: 'pointer' }} />
              </div>

              <div style={{ display: 'flex', gap: 10 }}>
                <button type="submit" disabled={editing} style={{
                  flex: 1, padding: '10px 0', cursor: editing ? 'default' : 'pointer',
                  background: editing ? 'rgba(var(--accent-rgb),0.07)' : 'rgba(var(--accent-rgb),0.12)',
                  border: '1px solid rgba(var(--accent-rgb),0.28)', borderRadius: 7, color: 'var(--accent)',
                  fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', transition: 'background 0.14s',
                }}>{editing ? 'SAVING…' : 'SAVE'}</button>
                <button type="button" onClick={() => setEditTarget(null)} disabled={editing} style={{
                  flex: 1, padding: '10px 0', cursor: 'pointer',
                  background: 'transparent', border: '1px solid var(--border)',
                  borderRadius: 7, color: 'var(--text-muted)', fontSize: 16, fontFamily: 'var(--font-mono)',
                }}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
