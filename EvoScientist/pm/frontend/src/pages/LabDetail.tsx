import React, { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, Lab } from '../api'
import { useAuth } from '../auth'

export function LabDetail() {
  const { id } = useParams<{ id: string }>()
  const { token, isAdmin } = useAuth()
  const navigate = useNavigate()

  const [lab, setLab] = useState<Lab | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState('')
  const [editDept, setEditDept] = useState('')
  const [editUni, setEditUni] = useState('')

  // Add member state
  const [showAdd, setShowAdd] = useState(false)
  const [addUserId, setAddUserId] = useState('')
  const [addRole, setAddRole] = useState('phd')
  const [addError, setAddError] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)

  useEffect(() => { load() }, [id, token])

  async function load() {
    if (!id || !token) return
    setLoading(true)
    try {
      const l = await api.getLab(id)
      setLab(l)
      setEditName(l.name)
      setEditDept(l.department)
      setEditUni(l.university)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load lab')
    } finally {
      setLoading(false)
    }
  }

  async function handleUpdate(e: React.FormEvent) {
    e.preventDefault()
    if (!lab) return
    try {
      const updated = await api.updateLab(lab.id, { name: editName, department: editDept, university: editUni })
      setLab(updated)
      setEditing(false)
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Update failed')
    }
  }

  async function handleAddMember(e: React.FormEvent) {
    e.preventDefault()
    if (!lab) return
    setAddError(null)
    setAdding(true)
    try {
      await api.addLabMember(lab.id, addUserId, addRole)
      setAddUserId('')
      setShowAdd(false)
      await load()
    } catch (err: unknown) {
      setAddError(err instanceof Error ? err.message : 'Failed to add member')
    } finally {
      setAdding(false)
    }
  }

  async function handleRemoveMember(userId: string) {
    if (!lab) return
    try {
      await api.removeLabMember(lab.id, userId)
      await load()
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to remove member')
    }
  }

  const roleColors: Record<string, string> = {
    pi: '#6366f1', postdoc: '#8b5cf6', phd: '#ff8015', ms: '#10b981', visitor: '#6b7280',
  }

  const inputStyle: React.CSSProperties = {
    padding: '9px 12px', background: 'var(--surface-input)',
    border: '1px solid var(--border)', borderRadius: 7,
    color: 'var(--text)', fontSize: 22, outline: 'none', width: '100%',
  }

  if (loading) return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', padding: 40, fontFamily: 'var(--font-mono)', fontSize: 19 }}>
      LOADING…
    </div>
  )
  if (error || !lab) return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: '#f43f5e', padding: 40, fontFamily: 'var(--font-mono)', fontSize: 19 }}>
      {error || 'Lab not found'}
    </div>
  )

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
          <button onClick={() => navigate('/labs')} style={{
            cursor: 'pointer', background: 'var(--surface-input)',
            border: '1px solid var(--border)', borderRadius: 6,
            color: 'var(--text-muted)', padding: '3px 9px', fontSize: 22, lineHeight: 1,
          }}>←</button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <img src="/sabita.jpg" alt="SABITA" style={{ height: 26, borderRadius: 4 }} />
            <span style={{ color: 'var(--text-dim)', fontSize: 20, fontFamily: 'var(--font-mono)' }}>/labs</span>
            <span style={{ color: 'var(--text-dim)', fontSize: 20 }}>/</span>
            <span style={{ color: '#ff8015', fontSize: 21, fontFamily: 'var(--font-mono)' }}>{lab.name}</span>
          </div>
        </div>
        <button onClick={() => navigate(`/labs/${id}/impact`)} style={{
          cursor: 'pointer', padding: '7px 14px',
          background: 'rgba(99,102,241,0.1)',
          border: '1px solid rgba(99,102,241,0.3)',
          borderRadius: 7, color: '#6366f1',
          fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', marginRight: 8,
        }}>📊 IMPACT</button>
        <button onClick={() => navigate(`/labs/${id}/wiki`)} style={{
          cursor: 'pointer', padding: '7px 14px',
          background: 'rgba(16,185,129,0.1)',
          border: '1px solid rgba(16,185,129,0.3)',
          borderRadius: 7, color: '#10b981',
          fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', marginRight: 8,
        }}>📖 WIKI</button>
        <button onClick={() => setEditing(e => !e)} style={{
          cursor: 'pointer', padding: '7px 16px',
          background: 'rgba(255,128,21,0.1)',
          border: '1px solid rgba(255,128,21,0.3)',
          borderRadius: 7, color: '#ff8015',
          fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em',
        }}>{editing ? 'CANCEL' : 'EDIT'}</button>
      </div>

      <div style={{ maxWidth: 680, margin: '0 auto', padding: '32px 28px' }}>
        {/* Info card */}
        <div style={{
          background: 'var(--surface-card)', border: '1px solid var(--border)',
          borderRadius: 10, padding: 24, marginBottom: 28,
        }}>
          {editing ? (
            <form onSubmit={handleUpdate}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
                <div>
                  <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.1em', fontFamily: 'var(--font-mono)' }}>NAME</label>
                  <input value={editName} onChange={e => setEditName(e.target.value)} required style={inputStyle} />
                </div>
                <div>
                  <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.1em', fontFamily: 'var(--font-mono)' }}>DEPARTMENT</label>
                  <input value={editDept} onChange={e => setEditDept(e.target.value)} style={inputStyle} />
                </div>
              </div>
              <div style={{ marginBottom: 20 }}>
                <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.1em', fontFamily: 'var(--font-mono)' }}>UNIVERSITY</label>
                <input value={editUni} onChange={e => setEditUni(e.target.value)} style={inputStyle} />
              </div>
              <button type="submit" style={{
                padding: '9px 24px', cursor: 'pointer',
                background: 'rgba(255,128,21,0.12)',
                border: '1px solid rgba(255,128,21,0.28)',
                borderRadius: 7, color: '#ff8015',
                fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)',
              }}>SAVE</button>
            </form>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
                <div style={{
                  width: 48, height: 48, borderRadius: 12,
                  background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 24, fontWeight: 700, color: '#fff',
                  fontFamily: 'var(--font-mono)',
                }}>{lab.name[0].toUpperCase()}</div>
                <div>
                  <div style={{ fontSize: 28, fontWeight: 600, color: 'var(--text-heading)' }}>{lab.name}</div>
                  <div style={{ fontSize: 18, color: 'var(--text-dim)', marginTop: 2 }}>
                    {lab.department}{lab.department && lab.university ? ' · ' : ''}{lab.university}
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 24, color: 'var(--text-2)', fontSize: 18, fontFamily: 'var(--font-mono)' }}>
                <span>PI: {lab.pi_id ? lab.members.find(m => m.role === 'pi')?.username ?? lab.pi_id : '—'}</span>
                <span>{lab.members.length} member{lab.members.length !== 1 ? 's' : ''}</span>
              </div>
            </>
          )}
        </div>

        {/* Members */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>
            MEMBERS ({lab.members.length})
          </div>
          <button onClick={() => { setShowAdd(true); setAddError(null) }} style={{
            cursor: 'pointer', padding: '5px 12px',
            background: 'rgba(255,128,21,0.1)',
            border: '1px solid rgba(255,128,21,0.3)', borderRadius: 6, color: '#ff8015',
            fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
          }}>+ ADD</button>
        </div>

        {showAdd && (
          <form onSubmit={handleAddMember} style={{
            background: 'var(--surface-card)', border: '1px solid rgba(255,128,21,0.2)',
            borderRadius: 10, padding: '16px 20px', marginBottom: 12,
          }}>
            {addError && (
              <div style={{ color: '#f43f5e', marginBottom: 10, fontSize: 17 }}>{addError}</div>
            )}
            <div style={{ display: 'flex', gap: 10, alignItems: 'end' }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-dim)', marginBottom: 4, fontFamily: 'var(--font-mono)' }}>USER ID</div>
                <input value={addUserId} onChange={e => setAddUserId(e.target.value)} required placeholder="user_id" style={inputStyle} />
              </div>
              <div style={{ width: 140 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-dim)', marginBottom: 4, fontFamily: 'var(--font-mono)' }}>ROLE</div>
                <select value={addRole} onChange={e => setAddRole(e.target.value)} style={{
                  ...inputStyle, padding: '8px 10px', cursor: 'pointer',
                }}>
                  <option value="pi">PI</option>
                  <option value="postdoc">Postdoc</option>
                  <option value="phd">PhD</option>
                  <option value="ms">MS</option>
                  <option value="visitor">Visitor</option>
                </select>
              </div>
              <button type="submit" disabled={adding} style={{
                padding: '9px 16px', cursor: adding ? 'default' : 'pointer',
                background: adding ? 'rgba(16,185,129,0.07)' : 'rgba(16,185,129,0.12)',
                border: '1px solid rgba(16,185,129,0.28)',
                borderRadius: 7, color: '#10b981',
                fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
                whiteSpace: 'nowrap', height: 44,
              }}>{adding ? '…' : 'ADD'}</button>
            </div>
          </form>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {lab.members.map(m => (
            <div key={m.user_id} style={{
              background: 'var(--surface-card)', border: '1px solid var(--border)',
              borderRadius: 10, padding: '14px 20px',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 38, height: 38, borderRadius: '50%',
                  background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 20, fontWeight: 700, color: '#fff',
                  fontFamily: 'var(--font-mono)',
                }}>{m.username[0].toUpperCase()}</div>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 500, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)' }}>
                    {m.username}
                  </div>
                  <div style={{ fontSize: 16, color: 'var(--text-dim)', marginTop: 2 }}>
                    {m.user_id}
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{
                  fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)',
                  color: roleColors[m.role] || '#6b7280',
                  background: `${roleColors[m.role] || '#6b7280'}14`,
                  border: `1px solid ${roleColors[m.role] || '#6b7280'}30`,
                  borderRadius: 4, padding: '2px 8px', letterSpacing: '0.06em',
                }}>{m.role.toUpperCase()}</span>
                <button onClick={() => handleRemoveMember(m.user_id)} style={{
                  cursor: 'pointer', padding: '4px 10px',
                  background: 'rgba(244,63,94,0.06)',
                  border: '1px solid rgba(244,63,94,0.15)', borderRadius: 5, color: '#f43f5e',
                  fontSize: 15, fontFamily: 'var(--font-mono)',
                }}>×</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
