import React, { useEffect, useState, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, Lab, LabMember_ } from '../api'
import { useAuth } from '../auth'
import { LAB_ROLES, assignableRoles, handoverCandidates, isLabPi, labPi, rosterLocked } from '../components/labs/labRoster'
import { LabDatasets } from '../components/labs/LabDatasets'

console.log('LabDetail MOUNTED v2')
export function LabDetail() {
  const { id } = useParams<{ id: string }>()
  const { token, isAdmin, username } = useAuth()
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
  const [userSearch, setUserSearch] = useState('')
  const [userResults, setUserResults] = useState<{ id: string; username: string }[]>([])
  const [searching, setSearching] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)

  // Roster management: role changes, a confirmed removal, and handing the lab to another member.
  const [rosterError, setRosterError] = useState<string | null>(null)
  const [busyMember, setBusyMember] = useState<string | null>(null)
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null)
  const [showHandover, setShowHandover] = useState(false)
  const [handoverTo, setHandoverTo] = useState('')
  const [formerPiRole, setFormerPiRole] = useState('pi')
  const [handingOver, setHandingOver] = useState(false)

  useEffect(() => { load() }, [id, token])

  useEffect(() => {
    if (userSearch.length < 1) { setUserResults([]); return }
    setSearching(true)
    const t = setTimeout(async () => {
      try {
        const res = await api.searchUsers(userSearch)
        setUserResults(res)
      } catch { setUserResults([]) }
      setSearching(false)
    }, 200)
    return () => clearTimeout(t)
  }, [userSearch])

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) setUserResults([])
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])

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
    setRosterError(null)
    setBusyMember(userId)
    try {
      await api.removeLabMember(lab.id, userId)
      setConfirmRemove(null)
      await load()
    } catch (err: unknown) {
      setRosterError(err instanceof Error ? err.message : 'Failed to remove member')
    } finally {
      setBusyMember(null)
    }
  }

  async function handleRoleChange(member: LabMember_, role: string) {
    if (!lab || role === member.role) return
    setRosterError(null)
    setBusyMember(member.user_id)
    try {
      await api.changeLabMemberRole(lab.id, member.user_id, role)
      await load()
    } catch (err: unknown) {
      setRosterError(err instanceof Error ? err.message : 'Failed to change the role')
    } finally {
      setBusyMember(null)
    }
  }

  // Hand the lab to another member. The server gives the new PI the 'pi' role with the title; the
  // former PI keeps theirs unless a different one is chosen here, applied as a second step (once
  // they are no longer the lab's PI the roster may change it). If that second step fails, the
  // handover itself has still happened — the lab is never left without a PI.
  async function handleHandover(e: React.FormEvent) {
    e.preventDefault()
    if (!lab || !handoverTo) return
    const former = labPi(lab)
    setRosterError(null)
    setHandingOver(true)
    let handedOver = false
    try {
      await api.updateLab(lab.id, { pi_id: handoverTo })
      handedOver = true
      if (former && formerPiRole !== former.role) {
        await api.changeLabMemberRole(lab.id, former.user_id, formerPiRole)
      }
      setShowHandover(false)
      setHandoverTo('')
      setFormerPiRole('pi')
    } catch (err: unknown) {
      const reason = err instanceof Error ? err.message : 'unknown error'
      const newPi = lab.members.find(m => m.user_id === handoverTo)?.username ?? 'the new PI'
      // Step one stands even when step two fails: say so, rather than "the handover failed".
      setRosterError(handedOver
        ? `The lab was handed to ${newPi}, but ${former?.username ?? 'the former PI'} keeps the PI role (${reason}). Change it from the list below.`
        : reason)
      if (handedOver) setShowHandover(false)
    } finally {
      setHandingOver(false)
      await load()
    }
  }

  const roleColors: Record<string, string> = {
    pi: '#6366f1', postdoc: '#8b5cf6', phd: '#ff8015', ms: '#10b981', visitor: '#6b7280',
  }

  const inputStyle: React.CSSProperties = {
    padding: '9px 12px', background: 'var(--surface-input)',
    border: '1px solid var(--border)', borderRadius: 7,
    color: 'var(--text)', fontSize: 17, outline: 'none', width: '100%',
  }

  if (loading) return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', padding: 40, fontFamily: 'var(--font-mono)', fontSize: 16 }}>
      Loading…
    </div>
  )
  if (error || !lab) return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: '#f43f5e', padding: 40, fontFamily: 'var(--font-mono)', fontSize: 16 }}>
      {error || 'Lab not found'}
    </div>
  )

  // The API says whether this caller may edit the lab and its roster (a 'pi'/
  // 'admin' member, or a platform admin). Without it the controls below only
  // produce 403s, so they stay hidden.
  const canManage = lab.can_manage || isAdmin
  const pi = labPi(lab)
  const mayHandOver = (isAdmin || isLabPi(lab, username)) && handoverCandidates(lab).length > 0

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <div className="page-header" style={{ maxWidth: 1100, margin: '0 auto', padding: '28px 32px 0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div>
            <div className="crumbs"><a href="/labs" onClick={e => { e.preventDefault(); navigate('/labs') }}>Labs</a><span aria-hidden>/</span></div>
            <h1 className="page-title">{lab.name}</h1>
          </div>
        </div>
        <button onClick={() => navigate(`/labs/${id}/impact`)} style={{
          cursor: 'pointer', padding: '7px 14px',
          background: 'rgba(99,102,241,0.1)',
          border: '1px solid rgba(99,102,241,0.3)',
          borderRadius: 7, color: '#6366f1',
          fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', marginRight: 8,
        }}>📊 Impact</button>
        <button onClick={() => navigate(`/labs/${id}/research-memory`)} className="btn" style={{ marginRight: 8 }}>Research memory</button>
        <button onClick={() => navigate(`/labs/${id}/wiki`)} style={{
          cursor: 'pointer', padding: '7px 14px',
          background: 'rgba(16,185,129,0.1)',
          border: '1px solid rgba(16,185,129,0.3)',
          borderRadius: 7, color: '#10b981',
          fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', marginRight: 8,
        }}>📖 Wiki</button>
        {canManage && (
          <button onClick={() => setEditing(e => !e)} style={{
            cursor: 'pointer', padding: '7px 16px',
            background: 'rgba(var(--accent-rgb),0.1)',
            border: '1px solid rgba(var(--accent-rgb),0.3)',
            borderRadius: 7, color: 'var(--accent)',
            fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em',
          }}>{editing ? 'Cancel' : 'Edit'}</button>
        )}
      </div>

      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0 32px 40px' }}>
        {/* Info card */}
        <div style={{
          background: 'var(--surface-card)', border: '1px solid var(--border)',
          borderRadius: 10, padding: 24, marginBottom: 28,
        }}>
          {editing && canManage ? (
            <form onSubmit={handleUpdate}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
                <div>
                  <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.04em', fontFamily: 'var(--font-mono)' }}>Name</label>
                  <input value={editName} onChange={e => setEditName(e.target.value)} required style={inputStyle} />
                </div>
                <div>
                  <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.04em', fontFamily: 'var(--font-mono)' }}>Department</label>
                  <input value={editDept} onChange={e => setEditDept(e.target.value)} style={inputStyle} />
                </div>
              </div>
              <div style={{ marginBottom: 20 }}>
                <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.04em', fontFamily: 'var(--font-mono)' }}>University</label>
                <input value={editUni} onChange={e => setEditUni(e.target.value)} style={inputStyle} />
              </div>
              <button type="submit" style={{
                padding: '9px 24px', cursor: 'pointer',
                background: 'rgba(var(--accent-rgb),0.12)',
                border: '1px solid rgba(var(--accent-rgb),0.28)',
                borderRadius: 7, color: 'var(--accent)',
                fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
              }}>Save</button>
            </form>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
                <div style={{
                  width: 48, height: 48, borderRadius: 12,
                  background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 20, fontWeight: 700, color: '#fff',
                  fontFamily: 'var(--font-mono)',
                }}>{lab.name[0].toUpperCase()}</div>
                <div>
                  <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--text-heading)' }}>{lab.name}</div>
                  <div style={{ fontSize: 15, color: 'var(--text-dim)', marginTop: 2 }}>
                    {lab.department}{lab.department && lab.university ? ' · ' : ''}{lab.university}
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 24, color: 'var(--text-2)', fontSize: 15, fontFamily: 'var(--font-mono)' }}>
                <span>PI: {pi?.username ?? (lab.pi_id || (lab.members.some(m => m.role === 'pi') ? 'not recorded (several members hold the PI role)' : '—'))}</span>
                <span>{lab.member_count} member{lab.member_count !== 1 ? 's' : ''}</span>
              </div>
            </>
          )}
        </div>

        {/* Members */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.04em' }}>
            MEMBERS ({lab.member_count})
          </div>
          {canManage && (
            <button onClick={() => { setShowAdd(true); setAddError(null) }} style={{
              cursor: 'pointer', padding: '5px 12px',
              background: 'rgba(var(--accent-rgb),0.1)',
              border: '1px solid rgba(var(--accent-rgb),0.3)', borderRadius: 6, color: 'var(--accent)',
              fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
            }}>+ Add</button>
          )}
        </div>

        {showAdd && canManage && (
          <form onSubmit={handleAddMember} style={{
            background: 'var(--surface-card)', border: '1px solid rgba(var(--accent-rgb),0.2)',
            borderRadius: 10, padding: '16px 20px', marginBottom: 12,
          }}>
            {addError && (
              <div style={{ color: '#f43f5e', marginBottom: 10, fontSize: 15 }}>{addError}</div>
            )}
            <div style={{ display: 'flex', gap: 10, alignItems: 'end' }}>
              <div style={{ flex: 1, position: 'relative' }} ref={searchRef}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-dim)', marginBottom: 4, fontFamily: 'var(--font-mono)' }}>User</div>
                <input
                  value={addUserId || userSearch}
                  onChange={e => { setUserSearch(e.target.value); setAddUserId('') }}
                  onFocus={() => { if (userSearch.length >= 1) { api.searchUsers(userSearch).then(setUserResults).catch(() => {}) } }}
                  required placeholder="Search username…"
                  style={inputStyle}
                />
                {userResults.length > 0 && (
                  <div style={{
                    position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 10,
                    background: 'var(--surface-panel)', border: '1px solid var(--border)',
                    borderRadius: 6, marginTop: 2, maxHeight: 200, overflowY: 'auto',
                  }}>
                    {userResults.map(u => (
                      <div key={u.id} onClick={() => {
                        setAddUserId(u.id)
                        setUserSearch(u.username)
                        setUserResults([])
                      }} style={{
                        padding: '8px 12px', cursor: 'pointer', fontSize: 15, color: 'var(--text)',
                        borderBottom: '1px solid var(--border-subtle)',
                        transition: 'background 0.1s',
                      }}
                        onMouseEnter={e => { e.currentTarget.style.background = 'var(--surface-input)' }}
                        onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
                      >{u.username} <span style={{ color: 'var(--text-dim)', fontSize: 14 }}>{u.id}</span></div>
                    ))}
                  </div>
                )}
              </div>
              <div style={{ width: 140 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-dim)', marginBottom: 4, fontFamily: 'var(--font-mono)' }}>Role</div>
                <select value={addRole} onChange={e => setAddRole(e.target.value)} style={{
                  ...inputStyle, padding: '8px 10px', cursor: 'pointer',
                }}>
                  {assignableRoles(lab, isAdmin).map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </div>
              <button type="submit" disabled={adding} style={{
                padding: '9px 16px', cursor: adding ? 'default' : 'pointer',
                background: adding ? 'rgba(16,185,129,0.07)' : 'rgba(16,185,129,0.12)',
                border: '1px solid rgba(16,185,129,0.28)',
                borderRadius: 7, color: '#10b981',
                fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
                whiteSpace: 'nowrap', height: 44,
              }}>{adding ? '…' : 'Add'}</button>
            </div>
          </form>
        )}

        {rosterError && <div className="msg msg-error" role="alert" style={{ marginBottom: 10 }}>{rosterError}</div>}

        {mayHandOver && (
          <div style={{ marginBottom: 12 }}>
            {!showHandover ? (
              <button type="button" className="btn" onClick={() => setShowHandover(true)}>Hand this lab to another member…</button>
            ) : (
              <form onSubmit={handleHandover} className="card" aria-label="Hand over the lab" style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '14px 18px' }}>
                <div style={{ fontWeight: 600 }}>Hand this lab to another member</div>
                <p className="hint" style={{ margin: 0 }}>
                  The new PI approves this lab&rsquo;s dataset requests, shares its datasets, and manages its members and ethics records.
                  {pi ? <> {pi.username} stops being the lab&rsquo;s PI.</> : null}
                </p>
                <label className="field"><span>New PI</span>
                  <select className="input" aria-label="New PI" value={handoverTo} onChange={e => setHandoverTo(e.target.value)} required>
                    <option value="">Choose a member…</option>
                    {handoverCandidates(lab).map(m => <option key={m.user_id} value={m.user_id}>{m.username} ({m.role})</option>)}
                  </select>
                </label>
                {pi && (
                  <label className="field"><span>{pi.username}&rsquo;s role afterwards</span>
                    <select className="input" aria-label="Former PI role" value={formerPiRole} onChange={e => setFormerPiRole(e.target.value)}>
                      {LAB_ROLES.map(r => <option key={r.value} value={r.value}>{r.value === 'pi' ? 'PI (stays a co-PI)' : r.label}</option>)}
                    </select>
                  </label>
                )}
                <div style={{ display: 'flex', gap: 8 }}>
                  <button type="submit" className="btn btn-primary" disabled={!handoverTo || handingOver}>{handingOver ? 'Handing over…' : 'Hand over'}</button>
                  <button type="button" className="btn" onClick={() => { setShowHandover(false); setHandoverTo('') }}>Cancel</button>
                </div>
              </form>
            )}
          </div>
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
                  fontSize: 16, fontWeight: 700, color: '#fff',
                  fontFamily: 'var(--font-mono)',
                }}>{m.username[0].toUpperCase()}</div>
                <div>
                  <div style={{ fontSize: 17, fontWeight: 500, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)' }}>
                    {m.username}
                  </div>
                  <div style={{ fontSize: 16, color: 'var(--text-dim)', marginTop: 2 }}>
                    {m.user_id}
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {pi?.user_id === m.user_id && <span className="chip" title="The lab's PI">Lab PI</span>}
                {canManage && !rosterLocked(lab, m, isAdmin) && assignableRoles(lab, isAdmin).some(r => r.value === m.role) ? (
                  <select className="input" aria-label={`Role of ${m.username}`} value={m.role}
                    disabled={busyMember === m.user_id}
                    onChange={e => handleRoleChange(m, e.target.value)}
                    style={{ width: 120, padding: '4px 8px', fontSize: 14 }}>
                    {assignableRoles(lab, isAdmin).map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                  </select>
                ) : (
                  <span title={canManage && rosterLocked(lab, m, isAdmin) ? 'Hand the lab to another member to change the PI' : undefined} style={{
                    fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)',
                    color: roleColors[m.role] || '#6b7280',
                    background: `${roleColors[m.role] || '#6b7280'}14`,
                    border: `1px solid ${roleColors[m.role] || '#6b7280'}30`,
                    borderRadius: 4, padding: '2px 8px', letterSpacing: '0.04em',
                  }}>{m.role.toUpperCase()}</span>
                )}
                {canManage && !rosterLocked(lab, m, isAdmin) && (
                  confirmRemove === m.user_id ? (
                    <span role="group" aria-label={`Confirm removing ${m.username}`} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14 }}>
                      <span className="hint">Remove {m.username}? They lose this lab&rsquo;s CVAT organisation and its datasets.</span>
                      <button type="button" className="btn" disabled={busyMember === m.user_id} onClick={() => handleRemoveMember(m.user_id)}
                        style={{ color: 'var(--rose)', borderColor: 'rgba(244,63,94,.35)' }}>Remove</button>
                      <button type="button" className="btn" onClick={() => setConfirmRemove(null)}>Cancel</button>
                    </span>
                  ) : (
                    <button aria-label={`Remove ${m.username}`} onClick={() => setConfirmRemove(m.user_id)} style={{
                      cursor: 'pointer', padding: '4px 10px',
                      background: 'rgba(244,63,94,0.06)',
                      border: '1px solid rgba(244,63,94,0.15)', borderRadius: 5, color: '#f43f5e',
                      fontSize: 15, fontFamily: 'var(--font-mono)',
                    }}>×</button>
                  )
                )}
              </div>
            </div>
          ))}
          {lab.members.length === 0 && lab.member_count > 0 && (
            <div style={{ color: 'var(--text-dim)', fontSize: 15, fontFamily: 'var(--font-mono)' }}>
              Roster visible to lab members only
            </div>
          )}
        </div>

        {/* Who can read each of this lab's datasets, and the revoke — for those allowed to revoke. */}
        {canManage && <LabDatasets labId={lab.id} isAdmin={isAdmin} />}
      </div>
    </div>
  )
}
