import React, { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, GRANT_BUDGET_CATEGORIES, GrantBudgetItem } from '../../api'
import { money } from './shared'

const inputStyle: React.CSSProperties = {
  padding: '8px 10px', background: 'var(--surface-input)',
  border: '1px solid var(--border)', borderRadius: 6,
  color: 'var(--text)', fontSize: 19, outline: 'none', width: '100%',
}

const smallBtn: React.CSSProperties = {
  cursor: 'pointer', padding: '5px 10px', borderRadius: 6,
  background: 'transparent', border: '1px solid var(--border)',
  color: 'var(--text-muted)', fontSize: 14,
  fontFamily: 'var(--font-mono)', fontWeight: 700,
}

type Draft = { category: string; description: string; planned_amount: string; spent_amount: string }

const emptyDraft: Draft = { category: 'personnel', description: '', planned_amount: '', spent_amount: '' }

export function GrantBudgetTab({ grantId, currency, canEdit }: {
  grantId: string; currency: string; canEdit: boolean
}) {
  const qc = useQueryClient()
  const [draft, setDraft] = useState<Draft | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editDraft, setEditDraft] = useState<Draft>(emptyDraft)
  const [error, setError] = useState<string | null>(null)

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['grant-budget', grantId],
    queryFn: () => api.listGrantBudget(grantId),
  })

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['grant-budget', grantId] })
    qc.invalidateQueries({ queryKey: ['grant-stats'] })
  }

  const create = useMutation({
    mutationFn: (d: Draft) => api.createGrantBudgetItem(grantId, {
      category: d.category,
      description: d.description || null,
      planned_amount: Number(d.planned_amount || 0),
      spent_amount: Number(d.spent_amount || 0),
    }),
    onSuccess: () => { refresh(); setDraft(null); setError(null) },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : 'Could not add the line'),
  })

  const update = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      api.updateGrantBudgetItem(grantId, id, data),
    onSuccess: () => { refresh(); setEditingId(null); setError(null) },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : 'Could not save the line'),
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteGrantBudgetItem(grantId, id),
    onSuccess: refresh,
  })

  const planned = items.reduce((s, i) => s + i.planned_amount, 0)
  const spent = items.reduce((s, i) => s + i.spent_amount, 0)
  const remaining = planned - spent
  const pct = planned > 0 ? Math.min(100, Math.round((spent / planned) * 100)) : 0
  const overspent = planned > 0 && spent > planned

  const startEdit = (item: GrantBudgetItem) => {
    setEditingId(item.id)
    setEditDraft({
      category: item.category,
      description: item.description ?? '',
      planned_amount: String(item.planned_amount),
      spent_amount: String(item.spent_amount),
    })
  }

  return (
    <div>
      {/* Summary */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12,
        background: 'var(--surface-card)', border: '1px solid var(--border)',
        borderRadius: 10, padding: '16px 20px', marginBottom: 16,
      }}>
        <Stat label="PLANNED" value={money(planned, currency)} />
        <Stat label="SPENT" value={money(spent, currency)} />
        <Stat
          label="REMAINING"
          value={money(remaining, currency)}
          color={overspent ? '#f43f5e' : '#10b981'}
        />
        <div style={{ gridColumn: '1 / -1' }}>
          <div style={{
            height: 6, borderRadius: 3, background: 'var(--surface-input)',
            overflow: 'hidden', marginTop: 4,
          }}>
            <div style={{
              width: `${pct}%`, height: '100%',
              background: overspent ? '#f43f5e' : '#ff8015',
              transition: 'width 0.2s',
            }} />
          </div>
          <div style={{
            fontSize: 14, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)',
            marginTop: 5, letterSpacing: '0.06em',
          }}>
            {pct}% OF BUDGET SPENT{overspent ? ' · OVER BUDGET' : ''}
          </div>
        </div>
      </div>

      {error && <Banner color="#f43f5e">{error}</Banner>}

      {canEdit && (
        draft ? (
          <div style={{
            background: 'var(--surface-card)', border: '1px solid rgba(255,128,21,0.2)',
            borderRadius: 10, padding: 16, marginBottom: 14,
          }}>
            <DraftFields
              draft={draft}
              setDraft={setDraft}
              onCancel={() => setDraft(null)}
              onSubmit={() => create.mutate(draft)}
              submitLabel="ADD LINE"
              busy={create.isPending}
            />
          </div>
        ) : (
          <button
            onClick={() => setDraft({ ...emptyDraft })}
            style={{
              ...smallBtn, marginBottom: 14, padding: '7px 14px',
              borderColor: 'rgba(255,128,21,0.3)', color: '#ff8015',
            }}
          >+ ADD BUDGET LINE</button>
        )
      )}

      {isLoading ? (
        <Muted>LOADING…</Muted>
      ) : items.length === 0 ? (
        <Muted>No budget lines yet.</Muted>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {items.map(item => (
            <div key={item.id} style={{
              background: 'var(--surface-card)', border: '1px solid var(--border)',
              borderRadius: 10, padding: '14px 18px',
            }}>
              {editingId === item.id ? (
                <DraftFields
                  draft={editDraft}
                  setDraft={setEditDraft}
                  onCancel={() => setEditingId(null)}
                  onSubmit={() => update.mutate({
                    id: item.id,
                    data: {
                      category: editDraft.category,
                      description: editDraft.description || null,
                      planned_amount: Number(editDraft.planned_amount || 0),
                      spent_amount: Number(editDraft.spent_amount || 0),
                    },
                  })}
                  submitLabel="SAVE"
                  busy={update.isPending}
                />
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{
                    fontSize: 14, fontFamily: 'var(--font-mono)', fontWeight: 700,
                    letterSpacing: '0.06em', color: '#ff8015',
                    background: 'rgba(255,128,21,0.1)', border: '1px solid rgba(255,128,21,0.25)',
                    borderRadius: 4, padding: '2px 8px', flexShrink: 0,
                  }}>{item.category.toUpperCase()}</span>
                  <span style={{ flex: 1, fontSize: 20, color: 'var(--text)' }}>
                    {item.description || '—'}
                  </span>
                  <span style={{ fontSize: 19, fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>
                    {money(item.spent_amount, currency)} / {money(item.planned_amount, currency)}
                  </span>
                  {canEdit && (
                    <span style={{ display: 'flex', gap: 6 }}>
                      <button style={smallBtn} onClick={() => startEdit(item)}>EDIT</button>
                      <button
                        style={{ ...smallBtn, borderColor: 'rgba(244,63,94,0.3)', color: '#f43f5e' }}
                        onClick={() => {
                          if (window.confirm('Delete this budget line?')) remove.mutate(item.id)
                        }}
                      >DELETE</button>
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function DraftFields({ draft, setDraft, onSubmit, onCancel, submitLabel, busy }: {
  draft: Draft
  setDraft: (d: Draft) => void
  onSubmit: () => void
  onCancel: () => void
  submitLabel: string
  busy: boolean
}) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
      <label style={labelStyle}>
        CATEGORY
        <select
          value={draft.category}
          onChange={e => setDraft({ ...draft, category: e.target.value })}
          style={inputStyle}
        >
          {GRANT_BUDGET_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </label>
      <label style={labelStyle}>
        DESCRIPTION
        <input
          value={draft.description}
          onChange={e => setDraft({ ...draft, description: e.target.value })}
          placeholder="what it covers"
          style={inputStyle}
        />
      </label>
      <label style={labelStyle}>
        PLANNED
        <input
          type="number" min="0" step="any"
          value={draft.planned_amount}
          onChange={e => setDraft({ ...draft, planned_amount: e.target.value })}
          placeholder="0"
          style={inputStyle}
        />
      </label>
      <label style={labelStyle}>
        SPENT
        <input
          type="number" min="0" step="any"
          value={draft.spent_amount}
          onChange={e => setDraft({ ...draft, spent_amount: e.target.value })}
          placeholder="0"
          style={inputStyle}
        />
      </label>
      <div style={{ gridColumn: '2 / -1', display: 'flex', gap: 8, alignItems: 'flex-end' }}>
        <button
          onClick={onSubmit}
          disabled={busy}
          style={{
            cursor: 'pointer', padding: '9px 20px', borderRadius: 7, border: 'none',
            background: busy ? 'rgba(255,128,21,0.4)' : '#ff8015', color: '#06091a',
            fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
          }}
        >{busy ? 'SAVING…' : submitLabel}</button>
        <button style={{ ...smallBtn, padding: '9px 14px' }} onClick={onCancel}>CANCEL</button>
      </div>
    </div>
  )
}

const labelStyle: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 5,
  fontSize: 14, fontWeight: 700, color: 'var(--text-dim)',
  fontFamily: 'var(--font-mono)', letterSpacing: '0.08em',
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div style={{
        fontSize: 13, fontWeight: 700, color: 'var(--text-dim)',
        fontFamily: 'var(--font-mono)', letterSpacing: '0.1em',
      }}>{label}</div>
      <div style={{ fontSize: 22, color: color ?? 'var(--text-heading)', marginTop: 3 }}>{value}</div>
    </div>
  )
}

function Muted({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      padding: '20px 0', color: 'var(--text-dim)',
      fontFamily: 'var(--font-mono)', fontSize: 18,
    }}>{children}</div>
  )
}

function Banner({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <div style={{
      padding: '8px 12px', marginBottom: 12,
      background: `${color}14`, border: `1px solid ${color}30`,
      borderRadius: 6, color, fontSize: 18, fontFamily: 'var(--font-mono)',
    }}>{children}</div>
  )
}
