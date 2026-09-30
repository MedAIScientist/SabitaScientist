import React, { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, GRANT_MEMBER_ROLES } from '../../api'
import { UserPicker } from './UserPicker'

const ROLE_COLORS: Record<string, string> = {
  pi: '#ff8015',
  co_pi: '#f59e0b',
  researcher: '#6366f1',
  assistant: '#10b981',
  advisor: '#8b5cf6',
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

export function GrantTeamTab({ grantId, canEdit }: { grantId: string; canEdit: boolean }) {
  const qc = useQueryClient()
  const [userId, setUserId] = useState<string | null>(null)
  const [role, setRole] = useState('researcher')
  const [share, setShare] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { data: members = [], isLoading } = useQuery({
    queryKey: ['grant-members', grantId],
    queryFn: () => api.listGrantMembers(grantId),
  })

  const refresh = () => qc.invalidateQueries({ queryKey: ['grant-members', grantId] })

  const add = useMutation({
    mutationFn: () => api.addGrantMember(grantId, {
      user_id: userId,
      role,
      share_percent: share === '' ? null : Number(share),
    }),
    onSuccess: () => {
      refresh(); setUserId(null); setShare(''); setRole('researcher'); setError(null)
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : 'Could not add the member'),
  })

  const update = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      api.updateGrantMember(grantId, id, data),
    onSuccess: refresh,
    onError: (e: unknown) => setError(e instanceof Error ? e.message : 'Could not save the member'),
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.removeGrantMember(grantId, id),
    onSuccess: refresh,
  })

  const totalShare = members.reduce((s, m) => s + (m.share_percent ?? 0), 0)

  return (
    <div>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
        marginBottom: 14,
      }}>
        <div style={{ fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
          {members.length} member{members.length !== 1 ? 's' : ''}
        </div>
        {totalShare > 0 && (
          <div style={{
            fontSize: 15, fontFamily: 'var(--font-mono)',
            color: totalShare > 100 ? '#f43f5e' : 'var(--text-dim)',
          }}>
            {totalShare}% ALLOCATED{totalShare > 100 ? ' · Over 100%' : ''}
          </div>
        )}
      </div>

      {error && (
        <div style={{
          padding: '8px 12px', marginBottom: 12, background: 'rgba(244,63,94,0.08)',
          border: '1px solid rgba(244,63,94,0.2)', borderRadius: 6, color: '#f43f5e',
          fontSize: 15, fontFamily: 'var(--font-mono)',
        }}>{error}</div>
      )}

      {canEdit && (
        <div style={{
          background: 'var(--surface-card)', border: '1px solid rgba(var(--accent-rgb),0.2)',
          borderRadius: 10, padding: 16, marginBottom: 16,
          display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 10, alignItems: 'end',
        }}>
          <label style={labelStyle}>
            Person
            <UserPicker value={userId} onChange={setUserId} placeholder="search by username…" />
          </label>
          <label style={labelStyle}>
            Role
            <select value={role} onChange={e => setRole(e.target.value)} style={inputStyle}>
              {GRANT_MEMBER_ROLES.map(r => <option key={r} value={r}>{r.replace('_', '-')}</option>)}
            </select>
          </label>
          <label style={labelStyle}>
            Share %
            <input
              type="number" min="0" max="100" step="any"
              value={share}
              onChange={e => setShare(e.target.value)}
              placeholder="optional"
              style={inputStyle}
            />
          </label>
          <div style={{ gridColumn: '1 / -1' }}>
            <button
              onClick={() => add.mutate()}
              disabled={!userId || add.isPending}
              style={{
                cursor: !userId ? 'default' : 'pointer', padding: '9px 20px',
                borderRadius: 7, border: 'none',
                background: !userId || add.isPending ? 'rgba(var(--accent-rgb),0.4)' : 'var(--accent)',
                color: '#fff', fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
              }}
            >{add.isPending ? 'Adding…' : 'Add to team'}</button>
          </div>
        </div>
      )}

      {isLoading ? (
        <Muted>Loading…</Muted>
      ) : members.length === 0 ? (
        <Muted>No team members yet.</Muted>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {members.map(m => (
            <div key={m.id} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              background: 'var(--surface-card)', border: '1px solid var(--border)',
              borderRadius: 10, padding: '14px 18px',
            }}>
              <div style={{
                width: 34, height: 34, borderRadius: '50%', flexShrink: 0,
                background: 'linear-gradient(135deg, #ff8015, #8b5cf6)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#fff', fontWeight: 700, fontSize: 16,
              }}>{(m.username ?? '?')[0]?.toUpperCase()}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 16, color: 'var(--text-heading)' }}>
                  {m.username ?? m.user_id.slice(0, 8)}
                </div>
                <div style={{
                  fontSize: 14, color: 'var(--text-dim)',
                  fontFamily: 'var(--font-mono)', marginTop: 2,
                }}>ADDED {m.added_at?.slice(0, 10)}</div>
              </div>
              <span style={{
                fontSize: 14, fontFamily: 'var(--font-mono)', fontWeight: 700,
                letterSpacing: '0.04em', color: ROLE_COLORS[m.role] ?? '#6b7280',
                background: `${ROLE_COLORS[m.role] ?? '#6b7280'}14`,
                border: `1px solid ${ROLE_COLORS[m.role] ?? '#6b7280'}30`,
                borderRadius: 4, padding: '2px 8px',
              }}>{m.role.replace('_', '-').toUpperCase()}</span>
              {canEdit ? (
                <>
                  <select
                    value={m.role}
                    onChange={e => update.mutate({ id: m.id, data: { role: e.target.value } })}
                    style={{ ...inputStyle, width: 120 }}
                  >
                    {GRANT_MEMBER_ROLES.map(r => (
                      <option key={r} value={r}>{r.replace('_', '-')}</option>
                    ))}
                  </select>
                  <input
                    type="number" min="0" max="100" step="any"
                    defaultValue={m.share_percent ?? ''}
                    placeholder="%"
                    onBlur={e => {
                      const v = e.target.value === '' ? null : Number(e.target.value)
                      if (v !== m.share_percent) {
                        update.mutate({ id: m.id, data: { share_percent: v } })
                      }
                    }}
                    style={{ ...inputStyle, width: 80 }}
                  />
                  <button
                    style={{ ...smallBtn, borderColor: 'rgba(244,63,94,0.3)', color: '#f43f5e' }}
                    onClick={() => {
                      if (window.confirm(`Remove ${m.username ?? 'this member'} from the team?`)) {
                        remove.mutate(m.id)
                      }
                    }}
                  >Remove</button>
                </>
              ) : (
                m.share_percent != null && (
                  <span style={{
                    fontSize: 15, fontFamily: 'var(--font-mono)', color: 'var(--text-2)',
                  }}>{m.share_percent}%</span>
                )
              )}
            </div>
          ))}
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
