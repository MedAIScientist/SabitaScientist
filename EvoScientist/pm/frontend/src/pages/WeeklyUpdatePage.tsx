import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { supervisionApi, WeeklyReport, WeeklyReportItem, api } from '../api'
import { useAuth } from '../auth'

function currentWeekStart(): string {
  const d = new Date()
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  const monday = new Date(d.setDate(diff))
  return monday.toISOString().slice(0, 10)
}

const ITEM_STATUSES = ['planned', 'in_progress', 'needs_review', 'done', 'blocked', 'waiting']

export function WeeklyUpdatePage() {
  const { role, isAdmin } = useAuth()
  const qc = useQueryClient()
  const week = currentWeekStart()
  const [draftItems, setDraftItems] = useState<Partial<WeeklyReportItem>[]>([])
  const [summary, setSummary] = useState({ accomplished: '', next_focus: '', support_requested: '' })
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const canSubmit = role === 'student' || isAdmin

  const { data: report, isLoading } = useQuery({
    queryKey: ['weekly-report', week],
    queryFn: () => supervisionApi.currentWeekReport(week),
    enabled: canSubmit,
  })

  useEffect(() => {
    if (!report) return
    setSummary({
      accomplished: report.accomplished || '',
      next_focus: report.next_focus || '',
      support_requested: report.support_requested || '',
    })
  }, [report?.id])

  // Seed editable items from server once
  useEffect(() => {
    if (report?.items?.length) {
      setDraftItems(report.items.map(i => ({ ...i })))
    }
  }, [report?.id])

  function updateDraft(idx: number, patch: Partial<WeeklyReportItem>) {
    setDraftItems(prev => prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)))
  }

  function addDraft() {
    setDraftItems(prev => [...prev, { item_title: '', progress_pct: 0, status: 'in_progress', needs_help: false, risk_level: 'low', sort_order: prev.length }])
  }

  async function saveAll(submit: boolean) {
    if (!report) return
    setSaving(true)
    setMsg(null)
    try {
      await supervisionApi.updateSummary(report.id, {
        accomplished: summary.accomplished,
        next_focus: summary.next_focus,
        support_requested: summary.support_requested,
      })
      for (const item of draftItems) {
        if (!item.item_title?.trim()) continue
        await supervisionApi.upsertItem(report.id, {
          item_id: item.id,
          item_title: item.item_title,
          item_kind: item.item_kind || undefined,
          progress_pct: item.progress_pct ?? 0,
          status: item.status || undefined,
          blocker: item.blocker || undefined,
          needs_help: !!item.needs_help,
          what_changed: item.what_changed || undefined,
          next_step: item.next_step || undefined,
          risk_level: item.risk_level || 'low',
          next_deadline: item.next_deadline || undefined,
          sort_order: item.sort_order ?? 0,
        })
      }
      if (submit) {
        await supervisionApi.submitReport(report.id)
        setMsg('Report submitted for review.')
      } else {
        setMsg('Draft saved.')
      }
      await qc.invalidateQueries({ queryKey: ['weekly-report', week] })
    } catch (e: any) {
      setMsg(e.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  if (!canSubmit) {
    return <div style={{ padding: 32 }}>Weekly updates are submitted by students. Open <strong>Reports</strong> to review submissions.</div>
  }
  if (isLoading) return <div style={{ padding: 32 }}>Loading this week’s report…</div>
  if (!report) return <div style={{ padding: 32 }}>No report available.</div>

  const locked = report.status === 'submitted'

  return (
    <div style={{ padding: '24px 32px', maxWidth: 960 }}>
      <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', color: 'var(--text-dim)' }}>Weekly update</div>
      <h1 style={{ margin: '4px 0 6px', fontSize: 22, color: 'var(--text-heading)' }}>Week of {week}</h1>
      <p style={{ color: 'var(--text-2)', margin: '0 0 18px', fontSize: 14 }}>
        Update each action point with structured fields. Status: <strong>{report.status}</strong>
        {locked && ' (locked for edits)'}
      </p>

      {msg && <div style={{ padding: '8px 12px', marginBottom: 14, borderRadius: 6, background: 'rgba(var(--accent-rgb),0.12)', border: '1px solid rgba(var(--accent-rgb),0.3)', fontSize: 14 }}>{msg}</div>}

      <section style={{ marginBottom: 22 }}>
        <h2 style={{ fontSize: 15, margin: '0 0 10px', color: 'var(--text-heading)' }}>Action-point updates</h2>
        {draftItems.map((item, idx) => (
          <div key={item.id || idx} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 14, marginBottom: 10, background: 'var(--surface-panel)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: 10, marginBottom: 8 }}>
              <input
                placeholder="Item title (paper, patent, task…)"
                value={item.item_title || ''}
                disabled={locked}
                onChange={e => updateDraft(idx, { item_title: e.target.value })}
                style={inputStyle}
              />
              <select disabled={locked} value={item.status || 'in_progress'} onChange={e => updateDraft(idx, { status: e.target.value })} style={inputStyle}>
                {ITEM_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <input
                type="number" min={0} max={100} placeholder="Progress %"
                value={item.progress_pct ?? 0}
                disabled={locked}
                onChange={e => updateDraft(idx, { progress_pct: Number(e.target.value) })}
                style={inputStyle}
              />
              <select disabled={locked} value={item.risk_level || 'low'} onChange={e => updateDraft(idx, { risk_level: e.target.value })} style={inputStyle}>
                {['low', 'medium', 'high', 'critical'].map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <textarea placeholder="What changed" value={item.what_changed || ''} disabled={locked} onChange={e => updateDraft(idx, { what_changed: e.target.value })} style={{ ...inputStyle, minHeight: 60 }} />
              <textarea placeholder="Next step" value={item.next_step || ''} disabled={locked} onChange={e => updateDraft(idx, { next_step: e.target.value })} style={{ ...inputStyle, minHeight: 60 }} />
            </div>
            <div style={{ display: 'flex', gap: 12, marginTop: 8, alignItems: 'center' }}>
              <label style={{ fontSize: 13, display: 'flex', gap: 6, alignItems: 'center' }}>
                <input type="checkbox" checked={!!item.needs_help} disabled={locked} onChange={e => updateDraft(idx, { needs_help: e.target.checked })} />
                Needs help
              </label>
              <input placeholder="Blocker (optional)" value={item.blocker || ''} disabled={locked} onChange={e => updateDraft(idx, { blocker: e.target.value })} style={{ ...inputStyle, flex: 1 }} />
            </div>
          </div>
        ))}
        {!locked && (
          <button onClick={addDraft} style={btnGhost}>+ Add item update</button>
        )}
      </section>

      <section style={{ marginBottom: 22 }}>
        <h2 style={{ fontSize: 15, margin: '0 0 10px', color: 'var(--text-heading)' }}>Short weekly summary</h2>
        <div style={{ display: 'grid', gap: 10 }}>
          <textarea placeholder="What I accomplished" value={summary.accomplished} disabled={locked} onChange={e => setSummary(s => ({ ...s, accomplished: e.target.value }))} style={{ ...inputStyle, minHeight: 70 }} />
          <textarea placeholder="What I will focus on next" value={summary.next_focus} disabled={locked} onChange={e => setSummary(s => ({ ...s, next_focus: e.target.value }))} style={{ ...inputStyle, minHeight: 70 }} />
          <textarea placeholder="Support or decision needed (optional)" value={summary.support_requested} disabled={locked} onChange={e => setSummary(s => ({ ...s, support_requested: e.target.value }))} style={{ ...inputStyle, minHeight: 70 }} />
        </div>
      </section>

      {!locked && (
        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={() => saveAll(false)} disabled={saving} style={btnPrimary}>{saving ? 'Saving…' : 'Save draft'}</button>
          <button onClick={() => saveAll(true)} disabled={saving} style={btnPrimary}>Submit for review</button>
        </div>
      )}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', fontSize: 14, fontFamily: 'var(--font-mono)',
  background: 'var(--surface-input)', border: '1px solid var(--border)',
  borderRadius: 5, color: 'var(--text)', boxSizing: 'border-box',
}

const btnPrimary: React.CSSProperties = {
  padding: '8px 16px', cursor: 'pointer', fontSize: 14, fontWeight: 700,
  background: 'var(--accent)', border: 'none', borderRadius: 6, color: '#1a1a1a',
}

const btnGhost: React.CSSProperties = {
  padding: '8px 14px', cursor: 'pointer', fontSize: 14,
  background: 'transparent', border: '1px dashed var(--border)',
  borderRadius: 6, color: 'var(--text-2)',
}
