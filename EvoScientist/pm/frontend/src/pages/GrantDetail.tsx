import React, { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, GRANT_STATUSES, Grant_, Lab, Project } from '../api'
import { CURRENCIES, STATUS_COLORS, daysUntil, money } from '../components/grant/shared'
import { UserPicker } from '../components/grant/UserPicker'
import { GrantBudgetTab } from '../components/grant/GrantBudgetTab'
import { GrantMilestonesTab } from '../components/grant/GrantMilestonesTab'
import { GrantTeamTab } from '../components/grant/GrantTeamTab'

type Tab = 'overview' | 'budget' | 'milestones' | 'team'

const TABS: { key: Tab; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'budget', label: 'Budget' },
  { key: 'milestones', label: 'Milestones' },
  { key: 'team', label: 'Team' },
]

const inputStyle: React.CSSProperties = {
  padding: '9px 12px', background: 'var(--surface-input)',
  border: '1px solid var(--border)', borderRadius: 7,
  color: 'var(--text)', fontSize: 16, outline: 'none', width: '100%',
}

const labelStyle: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 5,
  fontSize: 14, fontWeight: 700, color: 'var(--text-dim)',
  fontFamily: 'var(--font-mono)', letterSpacing: '0.04em',
}

type EditDraft = {
  title: string; funder: string; status: string
  amount_requested: string; amount_awarded: string; currency: string
  submitted_at: string; awarded_at: string; start_date: string; end_date: string
  description: string; lab_id: string; project_id: string; pi_id: string | null
}

const toDraft = (g: Grant_): EditDraft => ({
  title: g.title,
  funder: g.funder,
  status: g.status,
  amount_requested: g.amount_requested == null ? '' : String(g.amount_requested),
  amount_awarded: g.amount_awarded == null ? '' : String(g.amount_awarded),
  currency: g.currency,
  submitted_at: g.submitted_at?.slice(0, 10) ?? '',
  awarded_at: g.awarded_at?.slice(0, 10) ?? '',
  start_date: g.start_date?.slice(0, 10) ?? '',
  end_date: g.end_date?.slice(0, 10) ?? '',
  description: g.description ?? '',
  lab_id: g.lab_id ?? '',
  project_id: g.project_id ?? '',
  pi_id: g.pi_id,
})

export function GrantDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [tab, setTab] = useState<Tab>('overview')
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<EditDraft | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: grant, isLoading } = useQuery({
    queryKey: ['grant', id],
    queryFn: () => api.getGrant(id!),
    enabled: Boolean(id),
  })
  const { data: labs = [] } = useQuery<Lab[]>({ queryKey: ['labs'], queryFn: () => api.listLabs() })
  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects'], queryFn: () => api.listProjects(),
  })

  useEffect(() => {
    if (grant && !editing) setDraft(toDraft(grant))
  }, [grant, editing])

  const save = useMutation({
    mutationFn: (d: EditDraft) => api.updateGrant(id!, {
      title: d.title,
      funder: d.funder,
      status: d.status,
      amount_requested: d.amount_requested === '' ? null : Number(d.amount_requested),
      amount_awarded: d.amount_awarded === '' ? null : Number(d.amount_awarded),
      currency: d.currency,
      submitted_at: d.submitted_at || null,
      awarded_at: d.awarded_at || null,
      start_date: d.start_date || null,
      end_date: d.end_date || null,
      description: d.description || null,
      lab_id: d.lab_id || null,
      project_id: d.project_id || null,
      pi_id: d.pi_id,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['grant', id] })
      qc.invalidateQueries({ queryKey: ['grants'] })
      qc.invalidateQueries({ queryKey: ['grant-stats'] })
      setEditing(false); setError(null)
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : 'Could not save the grant'),
  })

  const remove = useMutation({
    mutationFn: () => api.deleteGrant(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['grants'] })
      qc.invalidateQueries({ queryKey: ['grant-stats'] })
      navigate('/grants')
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : 'Could not delete the grant'),
  })

  if (isLoading || !grant) {
    return (
      <div style={{
        padding: 40, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)',
      }}>Loading…</div>
    )
  }

  const canManage = grant.can_manage
  const left = daysUntil(grant.end_date)
  const d = draft ?? toDraft(grant)

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 28px' }}>

        <button
          onClick={() => navigate('/grants')}
          style={{
            cursor: 'pointer', background: 'var(--surface-input)',
            border: '1px solid var(--border)', borderRadius: 6,
            color: 'var(--text-muted)', padding: '3px 9px',
            fontSize: 17, lineHeight: 1, marginBottom: 16,
          }}
        >←</button>

        {/* Header */}
        <div style={{
          display: 'flex', justifyContent: 'space-between',
          alignItems: 'flex-start', gap: 16, marginBottom: 18,
        }}>
          <div style={{ flex: 1 }}>
            <h1 style={{
              margin: 0, fontSize: 24, fontWeight: 600, color: 'var(--text-heading)',
            }}>{grant.title}</h1>
            <div style={{ fontSize: 15, color: 'var(--text-dim)', marginTop: 5 }}>
              {grant.funder}
              {grant.pi_username ? ` · PI ${grant.pi_username}` : ''}
            </div>
            <div style={{
              display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap',
              fontSize: 15, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)',
            }}>
              <span style={{
                color: STATUS_COLORS[grant.status] ?? '#6b7280',
                background: `${STATUS_COLORS[grant.status] ?? '#6b7280'}14`,
                border: `1px solid ${STATUS_COLORS[grant.status] ?? '#6b7280'}30`,
                borderRadius: 4, padding: '2px 8px', fontWeight: 700,
              }}>{grant.status.replace('_', ' ').toUpperCase()}</span>
              {grant.amount_awarded != null && (
                <span>AWARDED {money(grant.amount_awarded, grant.currency)}</span>
              )}
              {grant.amount_requested != null && (
                <span>REQUESTED {money(grant.amount_requested, grant.currency)}</span>
              )}
              {left != null && (
                <span style={{ color: left < 0 ? '#f43f5e' : undefined }}>
                  {left < 0 ? `${Math.abs(left)}d PAST END` : `${left}d REMAINING`}
                </span>
              )}
            </div>
          </div>
          {canManage && (
            <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
              <button
                onClick={() => { setEditing(e => !e); setError(null) }}
                style={{
                  cursor: 'pointer', padding: '7px 16px',
                  background: editing ? 'rgba(16,185,129,0.12)' : 'rgba(var(--accent-rgb),0.1)',
                  border: `1px solid ${editing ? 'rgba(16,185,129,0.3)' : 'rgba(var(--accent-rgb),0.3)'}`,
                  borderRadius: 7, color: editing ? '#10b981' : 'var(--accent)',
                  fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
                }}
              >{editing ? 'Done' : 'Edit'}</button>
              <button
                onClick={() => {
                  if (window.confirm(`Delete "${grant.title}"? This also removes its budget, milestones and team.`)) {
                    remove.mutate()
                  }
                }}
                style={{
                  cursor: 'pointer', padding: '7px 16px', borderRadius: 7,
                  background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.25)',
                  color: '#f43f5e', fontSize: 16, fontWeight: 700,
                  fontFamily: 'var(--font-mono)',
                }}
              >Delete</button>
            </div>
          )}
        </div>

        {error && (
          <div style={{
            padding: '10px 14px', marginBottom: 16, background: 'rgba(244,63,94,0.08)',
            border: '1px solid rgba(244,63,94,0.2)', borderRadius: 7,
            color: '#f43f5e', fontSize: 16, fontFamily: 'var(--font-mono)',
          }}>{error}</div>
        )}

        {/* Tabs */}
        <div style={{
          display: 'flex', gap: 4, borderBottom: '1px solid var(--border)', marginBottom: 20,
        }}>
          {TABS.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              style={{
                cursor: 'pointer', padding: '9px 16px', background: 'transparent',
                border: 'none', borderBottom: `2px solid ${tab === t.key ? '#ff8015' : 'transparent'}`,
                color: tab === t.key ? 'var(--accent)' : 'var(--text-muted)',
                fontSize: 15, fontWeight: 700, letterSpacing: '0.04em',
                fontFamily: 'var(--font-mono)', marginBottom: -1,
              }}
            >{t.label}</button>
          ))}
        </div>

        {tab === 'overview' && (
          editing ? (
            <form
              onSubmit={e => { e.preventDefault(); save.mutate(d) }}
              style={{
                background: 'var(--surface-card)', border: '1px solid rgba(var(--accent-rgb),0.2)',
                borderRadius: 10, padding: 20,
              }}
            >
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <label style={labelStyle}>
                  Title
                  <input
                    required value={d.title}
                    onChange={e => setDraft({ ...d, title: e.target.value })} style={inputStyle}
                  />
                </label>
                <label style={labelStyle}>
                  Funder
                  <input
                    required value={d.funder}
                    onChange={e => setDraft({ ...d, funder: e.target.value })} style={inputStyle}
                  />
                </label>
                <label style={labelStyle}>
                  Status
                  <select
                    value={d.status}
                    onChange={e => setDraft({ ...d, status: e.target.value })} style={inputStyle}
                  >
                    {GRANT_STATUSES.map(s => (
                      <option key={s} value={s}>{s.replace('_', ' ')}</option>
                    ))}
                  </select>
                </label>
                <label style={labelStyle}>
                  Currency
                  <select
                    value={d.currency}
                    onChange={e => setDraft({ ...d, currency: e.target.value })} style={inputStyle}
                  >
                    {CURRENCIES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </label>
                <label style={labelStyle}>
                  Amount requested
                  <input
                    type="number" min="0" step="any" value={d.amount_requested}
                    onChange={e => setDraft({ ...d, amount_requested: e.target.value })}
                    style={inputStyle}
                  />
                </label>
                <label style={labelStyle}>
                  Amount awarded
                  <input
                    type="number" min="0" step="any" value={d.amount_awarded}
                    onChange={e => setDraft({ ...d, amount_awarded: e.target.value })}
                    style={inputStyle}
                  />
                </label>
                <label style={labelStyle}>
                  Submitted
                  <input
                    type="date" value={d.submitted_at}
                    onChange={e => setDraft({ ...d, submitted_at: e.target.value })} style={inputStyle}
                  />
                </label>
                <label style={labelStyle}>
                  Awarded on
                  <input
                    type="date" value={d.awarded_at}
                    onChange={e => setDraft({ ...d, awarded_at: e.target.value })} style={inputStyle}
                  />
                </label>
                <label style={labelStyle}>
                  Start date
                  <input
                    type="date" value={d.start_date}
                    onChange={e => setDraft({ ...d, start_date: e.target.value })} style={inputStyle}
                  />
                </label>
                <label style={labelStyle}>
                  End date
                  <input
                    type="date" value={d.end_date}
                    onChange={e => setDraft({ ...d, end_date: e.target.value })} style={inputStyle}
                  />
                </label>
                <label style={labelStyle}>
                  PI
                  <UserPicker
                    value={d.pi_id}
                    valueLabel={grant.pi_username}
                    onChange={pid => setDraft({ ...d, pi_id: pid })}
                  />
                </label>
                <label style={labelStyle}>
                  Lab
                  <select
                    value={d.lab_id}
                    onChange={e => setDraft({ ...d, lab_id: e.target.value })} style={inputStyle}
                  >
                    <option value="">— none —</option>
                    {labs.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
                  </select>
                </label>
                <label style={labelStyle}>
                  Project
                  <select
                    value={d.project_id}
                    onChange={e => setDraft({ ...d, project_id: e.target.value })} style={inputStyle}
                  >
                    <option value="">— none —</option>
                    {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </label>
                <label style={{ ...labelStyle, gridColumn: '1 / -1' }}>
                  Description
                  <textarea
                    value={d.description}
                    onChange={e => setDraft({ ...d, description: e.target.value })}
                    rows={4}
                    style={{ ...inputStyle, resize: 'vertical', fontFamily: 'inherit' }}
                  />
                </label>
              </div>
              <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
                <button
                  type="submit"
                  disabled={save.isPending}
                  style={{
                    padding: '9px 24px', cursor: 'pointer', border: 'none', borderRadius: 7,
                    background: save.isPending ? 'rgba(var(--accent-rgb),0.4)' : 'var(--accent)',
                    color: '#fff', fontSize: 15, fontWeight: 700,
                    fontFamily: 'var(--font-mono)',
                  }}
                >{save.isPending ? 'Saving…' : 'Save'}</button>
                <button
                  type="button"
                  onClick={() => { setEditing(false); setDraft(toDraft(grant)); setError(null) }}
                  style={{
                    padding: '9px 18px', cursor: 'pointer', borderRadius: 7,
                    background: 'transparent', border: '1px solid var(--border)',
                    color: 'var(--text-muted)', fontSize: 16, fontFamily: 'var(--font-mono)',
                  }}
                >Cancel</button>
              </div>
            </form>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <InfoRow label="Status" value={grant.status.replace('_', ' ')} />
              <InfoRow
                label="Amount awarded"
                value={grant.amount_awarded != null ? money(grant.amount_awarded, grant.currency) : '—'}
              />
              <InfoRow
                label="Amount requested"
                value={grant.amount_requested != null ? money(grant.amount_requested, grant.currency) : '—'}
              />
              <InfoRow label="PI" value={grant.pi_username ?? '—'} />
              <InfoRow label="Submitted" value={grant.submitted_at?.slice(0, 10) ?? '—'} />
              <InfoRow label="Awarded on" value={grant.awarded_at?.slice(0, 10) ?? '—'} />
              <InfoRow label="Start date" value={grant.start_date?.slice(0, 10) ?? '—'} />
              <InfoRow label="End date" value={grant.end_date?.slice(0, 10) ?? '—'} />
              <InfoRow label="Lab" value={labs.find(l => l.id === grant.lab_id)?.name ?? '—'} />
              <InfoRow label="Project" value={projects.find(p => p.id === grant.project_id)?.name ?? '—'} />
              <InfoRow label="Created" value={grant.created_at?.slice(0, 10) ?? '—'} />
              <InfoRow label="Updated" value={grant.updated_at?.slice(0, 10) ?? '—'} />
              {grant.description && (
                <div style={{ gridColumn: '1 / -1' }}>
                  <div style={{
                    fontSize: 14, fontWeight: 700, color: 'var(--text-dim)',
                    fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', marginBottom: 4,
                  }}>Description</div>
                  <div style={{ fontSize: 16, color: 'var(--text-2)', whiteSpace: 'pre-wrap' }}>
                    {grant.description}
                  </div>
                </div>
              )}
            </div>
          )
        )}

        {tab === 'budget' && (
          <GrantBudgetTab grantId={grant.id} currency={grant.currency} canEdit={canManage} />
        )}
        {tab === 'milestones' && (
          <GrantMilestonesTab grantId={grant.id} canEdit={canManage} />
        )}
        {tab === 'team' && <GrantTeamTab grantId={grant.id} canEdit={canManage} />}
      </div>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{
        fontSize: 14, fontWeight: 700, color: 'var(--text-dim)',
        fontFamily: 'var(--font-mono)', letterSpacing: '0.04em',
      }}>{label.toUpperCase()}</div>
      <div style={{ fontSize: 16, color: 'var(--text-2)', marginTop: 2 }}>{value}</div>
    </div>
  )
}
