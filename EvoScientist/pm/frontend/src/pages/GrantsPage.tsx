import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, GRANT_STATUSES, Lab, Project } from '../api'
import { CURRENCIES, SORT_OPTIONS, STATUS_COLORS, daysUntil, money, totalsLine } from '../components/grant/shared'
import { UserPicker } from '../components/grant/UserPicker'

const inputStyle: React.CSSProperties = {
  padding: '9px 12px', background: 'var(--surface-input)',
  border: '1px solid var(--border)', borderRadius: 7,
  color: 'var(--text)', fontSize: 20, outline: 'none', width: '100%',
}

const labelStyle: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 5,
  fontSize: 14, fontWeight: 700, color: 'var(--text-dim)',
  fontFamily: 'var(--font-mono)', letterSpacing: '0.08em',
}

type CreateDraft = {
  title: string; funder: string; status: string
  amount_requested: string; amount_awarded: string; currency: string
  submitted_at: string; start_date: string; end_date: string
  description: string
  lab_id: string; project_id: string; pi_id: string | null
}

const emptyCreate: CreateDraft = {
  title: '', funder: '', status: 'draft',
  amount_requested: '', amount_awarded: '', currency: 'TRY',
  submitted_at: '', start_date: '', end_date: '', description: '',
  lab_id: '', project_id: '', pi_id: null,
}

export function GrantsPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [showForm, setShowForm] = useState(false)
  const [draft, setDraft] = useState<CreateDraft>({ ...emptyCreate })
  const [error, setError] = useState<string | null>(null)

  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [sort, setSort] = useState('-created_at')

  const { data: grants = [], isLoading } = useQuery({
    queryKey: ['grants', q, status, sort],
    queryFn: () => api.listGrants({ q: q || undefined, status: status || undefined, sort }),
  })

  const { data: stats } = useQuery({
    queryKey: ['grant-stats'],
    queryFn: () => api.grantStats(),
  })

  const { data: labs = [] } = useQuery<Lab[]>({ queryKey: ['labs'], queryFn: () => api.listLabs() })
  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects'], queryFn: () => api.listProjects(),
  })

  const create = useMutation({
    mutationFn: () => api.createGrant({
      title: draft.title,
      funder: draft.funder,
      status: draft.status,
      amount_requested: draft.amount_requested === '' ? null : Number(draft.amount_requested),
      amount_awarded: draft.amount_awarded === '' ? null : Number(draft.amount_awarded),
      currency: draft.currency,
      submitted_at: draft.submitted_at || null,
      start_date: draft.start_date || null,
      end_date: draft.end_date || null,
      description: draft.description || null,
      lab_id: draft.lab_id || null,
      project_id: draft.project_id || null,
      pi_id: draft.pi_id,
    }),
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: ['grants'] })
      qc.invalidateQueries({ queryKey: ['grant-stats'] })
      setDraft({ ...emptyCreate })
      setShowForm(false)
      setError(null)
      navigate(`/grants/${created.id}`)
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : 'Could not create the grant'),
  })

  const set = <K extends keyof CreateDraft>(key: K, value: CreateDraft[K]) =>
    setDraft(d => ({ ...d, [key]: value }))

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <div style={{ maxWidth: 960, margin: '0 auto', padding: '32px 28px' }}>
        <div style={{
          display: 'flex', justifyContent: 'space-between',
          alignItems: 'center', marginBottom: 20,
        }}>
          <div>
            <h1 style={{
              margin: 0, fontSize: 30, fontWeight: 600,
              fontFamily: 'var(--font-mono)', color: 'var(--text-heading)',
            }}>Grants</h1>
            <p style={{
              margin: '4px 0 0', fontSize: 16, color: 'var(--text-dim)',
              fontFamily: 'var(--font-mono)',
            }}>{grants.length} SHOWN</p>
          </div>
          <button
            onClick={() => setShowForm(f => !f)}
            style={{
              cursor: 'pointer', padding: '7px 16px',
              background: 'rgba(255,128,21,0.1)', border: '1px solid rgba(255,128,21,0.3)',
              borderRadius: 7, color: '#ff8015', fontSize: 18, fontWeight: 700,
              fontFamily: 'var(--font-mono)',
            }}
          >+ NEW</button>
        </div>

        {/* Stats */}
        {stats && stats.total > 0 && (
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: 12, marginBottom: 20,
          }}>
            <StatCard label="GRANTS" value={String(stats.total)} />
            <StatCard
              label="AWARDED"
              value={totalsLine(stats.totals_by_currency, 'awarded')}
              hint={`${totalsLine(stats.totals_by_currency, 'requested')} requested`}
            />
            <StatCard
              label="SUCCESS RATE"
              value={stats.success_rate == null ? '—' : `${Math.round(stats.success_rate * 100)}%`}
              hint={`${stats.won} of ${stats.decided} decided`}
            />
            <StatCard
              label="ENDING SOON"
              value={String(stats.ending_soon)}
              hint="within 90 days"
              color={stats.ending_soon > 0 ? '#f59e0b' : undefined}
            />
            <StatCard
              label="OVERDUE"
              value={String(stats.overdue_milestones)}
              hint={`${stats.open_reports} open report${stats.open_reports === 1 ? '' : 's'}`}
              color={stats.overdue_milestones > 0 ? '#f43f5e' : undefined}
            />
            {stats.budget_planned > 0 && (
              <StatCard
                label="BUDGET SPENT"
                value={`${Math.round((stats.budget_spent / stats.budget_planned) * 100)}%`}
                hint="across all grants"
                color={stats.budget_spent > stats.budget_planned ? '#f43f5e' : undefined}
              />
            )}
          </div>
        )}

        {/* Create form */}
        {showForm && (
          <form
            onSubmit={e => { e.preventDefault(); create.mutate() }}
            style={{
              background: 'var(--surface-card)', border: '1px solid rgba(255,128,21,0.2)',
              borderRadius: 10, padding: 24, marginBottom: 20,
            }}
          >
            {error && (
              <div style={{
                padding: '8px 12px', marginBottom: 14, background: 'rgba(244,63,94,0.08)',
                border: '1px solid rgba(244,63,94,0.2)', borderRadius: 6,
                color: '#f43f5e', fontSize: 18, fontFamily: 'var(--font-mono)',
              }}>{error}</div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <label style={labelStyle}>
                TITLE *
                <input
                  required value={draft.title}
                  onChange={e => set('title', e.target.value)}
                  placeholder="Project title" style={inputStyle}
                />
              </label>
              <label style={labelStyle}>
                FUNDER *
                <input
                  required value={draft.funder}
                  onChange={e => set('funder', e.target.value)}
                  placeholder="TÜBİTAK, TÜSEB, NIH…" style={inputStyle}
                />
              </label>
              <label style={labelStyle}>
                STATUS
                <select
                  value={draft.status}
                  onChange={e => set('status', e.target.value)}
                  style={inputStyle}
                >
                  {GRANT_STATUSES.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
                </select>
              </label>
              <label style={labelStyle}>
                CURRENCY
                <select
                  value={draft.currency}
                  onChange={e => set('currency', e.target.value)}
                  style={inputStyle}
                >
                  {CURRENCIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
              <label style={labelStyle}>
                AMOUNT REQUESTED
                <input
                  type="number" min="0" step="any" value={draft.amount_requested}
                  onChange={e => set('amount_requested', e.target.value)}
                  placeholder="0" style={inputStyle}
                />
              </label>
              <label style={labelStyle}>
                AMOUNT AWARDED
                <input
                  type="number" min="0" step="any" value={draft.amount_awarded}
                  onChange={e => set('amount_awarded', e.target.value)}
                  placeholder="0" style={inputStyle}
                />
              </label>
              <label style={labelStyle}>
                SUBMITTED
                <input
                  type="date" value={draft.submitted_at}
                  onChange={e => set('submitted_at', e.target.value)} style={inputStyle}
                />
              </label>
              <label style={labelStyle}>
                START DATE
                <input
                  type="date" value={draft.start_date}
                  onChange={e => set('start_date', e.target.value)} style={inputStyle}
                />
              </label>
              <label style={labelStyle}>
                END DATE
                <input
                  type="date" value={draft.end_date}
                  onChange={e => set('end_date', e.target.value)} style={inputStyle}
                />
              </label>
              <label style={labelStyle}>
                PI
                <UserPicker
                  value={draft.pi_id}
                  onChange={id => set('pi_id', id)}
                  placeholder="search by username…"
                />
              </label>
              <label style={labelStyle}>
                LAB
                <select
                  value={draft.lab_id}
                  onChange={e => set('lab_id', e.target.value)} style={inputStyle}
                >
                  <option value="">— none —</option>
                  {labs.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
                </select>
              </label>
              <label style={labelStyle}>
                PROJECT
                <select
                  value={draft.project_id}
                  onChange={e => set('project_id', e.target.value)} style={inputStyle}
                >
                  <option value="">— none —</option>
                  {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </label>
              <label style={{ ...labelStyle, gridColumn: '1 / -1' }}>
                DESCRIPTION
                <textarea
                  value={draft.description}
                  onChange={e => set('description', e.target.value)}
                  rows={3}
                  placeholder="scope, objectives, consortium…"
                  style={{ ...inputStyle, resize: 'vertical', fontFamily: 'inherit' }}
                />
              </label>
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
              <button
                type="submit"
                disabled={create.isPending}
                style={{
                  padding: '9px 24px', cursor: 'pointer', border: 'none', borderRadius: 7,
                  background: create.isPending ? 'rgba(255,128,21,0.4)' : '#ff8015',
                  color: '#06091a', fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)',
                }}
              >{create.isPending ? 'CREATING…' : 'CREATE'}</button>
              <button
                type="button"
                onClick={() => { setShowForm(false); setError(null) }}
                style={{
                  padding: '9px 18px', cursor: 'pointer', borderRadius: 7,
                  background: 'transparent', border: '1px solid var(--border)',
                  color: 'var(--text-muted)', fontSize: 16, fontFamily: 'var(--font-mono)',
                }}
              >CANCEL</button>
            </div>
          </form>
        )}

        {/* Filters */}
        <div style={{
          display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 10, marginBottom: 16,
        }}>
          <input
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="search title, funder or description…"
            style={inputStyle}
          />
          <select value={status} onChange={e => setStatus(e.target.value)} style={inputStyle}>
            <option value="">all statuses</option>
            {GRANT_STATUSES.map(s => (
              <option key={s} value={s}>{s.replace('_', ' ')}</option>
            ))}
          </select>
          <select value={sort} onChange={e => setSort(e.target.value)} style={inputStyle}>
            {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        {/* List */}
        {isLoading ? (
          <div style={{
            padding: 40, textAlign: 'center', color: 'var(--text-dim)',
            fontFamily: 'var(--font-mono)',
          }}>LOADING…</div>
        ) : grants.length === 0 ? (
          <div style={{
            padding: 40, textAlign: 'center', color: 'var(--text-dim)',
            fontFamily: 'var(--font-mono)', fontSize: 18,
          }}>
            {q || status ? 'No grants match these filters.' : 'No grants yet.'}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {grants.map(g => {
              const left = daysUntil(g.end_date)
              const endingSoon =
                left != null && left >= 0 && left <= 90 &&
                (g.status === 'active' || g.status === 'awarded')
              return (
                <div
                  key={g.id}
                  onClick={() => navigate(`/grants/${g.id}`)}
                  style={{
                    background: 'var(--surface-card)',
                    border: '1px solid var(--border)',
                    borderLeft: `3px solid ${STATUS_COLORS[g.status] ?? '#6b7280'}`,
                    borderRadius: '0 10px 10px 0', padding: '16px 20px',
                    cursor: 'pointer',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(255,128,21,0.35)' }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-heading)' }}>
                        {g.title}
                      </div>
                      <div style={{ fontSize: 17, color: 'var(--text-2)', marginTop: 3 }}>
                        {g.funder}
                        {g.pi_username ? ` · PI ${g.pi_username}` : ''}
                      </div>
                      <div style={{
                        fontSize: 15, color: 'var(--text-dim)',
                        fontFamily: 'var(--font-mono)', marginTop: 5,
                      }}>
                        {g.amount_awarded != null
                          ? `AWARDED ${money(g.amount_awarded, g.currency)}`
                          : g.amount_requested != null
                            ? `REQUESTED ${money(g.amount_requested, g.currency)}`
                            : 'NO AMOUNT'}
                        {g.end_date ? ` · ENDS ${g.end_date.slice(0, 10)}` : ''}
                        {endingSoon ? ` · ${left}d LEFT` : ''}
                      </div>
                    </div>
                    <span style={{
                      fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)',
                      color: STATUS_COLORS[g.status] ?? '#6b7280',
                      background: `${STATUS_COLORS[g.status] ?? '#6b7280'}14`,
                      border: `1px solid ${STATUS_COLORS[g.status] ?? '#6b7280'}30`,
                      borderRadius: 4, padding: '2px 8px', whiteSpace: 'nowrap',
                    }}>{g.status.replace('_', ' ').toUpperCase()}</span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, hint, color }: {
  label: string; value: string; hint?: string; color?: string
}) {
  return (
    <div style={{
      background: 'var(--surface-card)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '14px 16px',
    }}>
      <div style={{
        fontSize: 13, fontWeight: 700, color: 'var(--text-dim)',
        fontFamily: 'var(--font-mono)', letterSpacing: '0.1em',
      }}>{label}</div>
      <div style={{
        fontSize: 21, color: color ?? 'var(--text-heading)', marginTop: 4,
        overflowWrap: 'anywhere',
      }}>{value}</div>
      {hint && (
        <div style={{
          fontSize: 13, color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)', marginTop: 3,
        }}>{hint}</div>
      )}
    </div>
  )
}
