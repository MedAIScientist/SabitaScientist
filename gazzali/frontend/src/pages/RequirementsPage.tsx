import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { supervisionApi } from '../api'
import { useAuth } from '../auth'

const LEVELS = ['BSc', 'MSc', 'PhD', 'Postdoc', 'IR', 'Other']
// Publication-only platform: course credits and GPA are not tracked here, so the
// two transcript-based requirement types are no longer offered.
const TYPES = ['research_item', 'milestone', 'custom']
// Values the readiness calculation recognises (anything else counts all publications).
const ITEM_TYPES = ['', 'Journal Paper', 'Conference Paper']

// Common requirement kinds to start from. They only fill the form: the admin sets the
// programme's real numbers before adding. Nothing here is saved automatically.
const STARTERS: { label: string; req_type: string; research_item_type: string; title: string; unit: string }[] = [
  { label: 'Journal papers', req_type: 'research_item', research_item_type: 'Journal Paper', title: 'Journal publications', unit: 'papers' },
  { label: 'Conference papers', req_type: 'research_item', research_item_type: 'Conference Paper', title: 'Conference publications', unit: 'papers' },
  { label: 'Any publications', req_type: 'research_item', research_item_type: '', title: 'Publications', unit: 'papers' },
  { label: 'Thesis proposal', req_type: 'milestone', research_item_type: '', title: 'Thesis proposal approved', unit: '' },
  { label: 'Qualifying exam', req_type: 'milestone', research_item_type: '', title: 'Qualifying exam passed', unit: '' },
  { label: 'Thesis defence', req_type: 'milestone', research_item_type: '', title: 'Thesis defended', unit: '' },
]

export function RequirementsPage() {
  const qc = useQueryClient()
  const { isAdmin } = useAuth()
  const [level, setLevel] = useState('All')
  const [form, setForm] = useState({
    level: 'PhD', req_type: 'research_item', title: '', description: '',
    research_item_type: '', target_value: '1', unit: '', required: true,
  })
  const [msg, setMsg] = useState<string | null>(null)

  const { data: requirements, isLoading } = useQuery({
    queryKey: ['requirements', level],
    queryFn: () => supervisionApi.listRequirements(level === 'All' ? undefined : level),
  })

  async function createRequirement() {
    if (!form.title.trim()) return setMsg('Title is required')
    try {
      await supervisionApi.createRequirement({
        level: form.level,
        title: form.title,
        req_type: form.req_type,
        description: form.description || undefined,
        research_item_type: form.research_item_type || undefined,
        target_value: Number(form.target_value) || 1,
        unit: form.unit || undefined,
        required: form.required,
      })
      setMsg('Requirement added.')
      setForm(f => ({ ...f, title: '', description: '', research_item_type: '', unit: '' }))
      await qc.invalidateQueries({ queryKey: ['requirements'] })
    } catch (e: any) {
      setMsg(e.message)
    }
  }

  async function archive(id: string) {
    try {
      await supervisionApi.archiveRequirement(id)
      setMsg('Requirement archived.')
      await qc.invalidateQueries({ queryKey: ['requirements'] })
    } catch (e: any) {
      setMsg(e.message)
    }
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1100 }}>
      <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', color: 'var(--text-dim)' }}>Administration</div>
      <h1 style={{ margin: '4px 0 6px', fontSize: 22, color: 'var(--text-heading)' }}>Graduation requirements</h1>
      <p style={{ color: 'var(--text-2)', margin: '0 0 18px', fontSize: 14 }}>
        Define reusable, year-independent requirements for every study level. Remove archives — it never deletes student progress.
      </p>

      {msg && <div style={{ padding: '8px 12px', marginBottom: 14, borderRadius: 6, background: 'rgba(var(--accent-rgb),0.12)', border: '1px solid rgba(var(--accent-rgb),0.3)' }}>{msg}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 22 }}>
        <div>
          <div style={{ marginBottom: 12 }}>
            <select value={level} onChange={e => setLevel(e.target.value)} style={{ ...inputStyle, width: 200 }}>
              <option value="All">All levels</option>
              {LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          </div>

          {isLoading ? <div>Loading…</div> : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
              <thead>
                <tr>
                  {['Level', 'Requirement', 'Type', 'Target', 'Required', ''].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '8px 10px', borderBottom: '1px solid var(--border)', color: 'var(--text-dim)', fontSize: 12 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(requirements || []).map(r => (
                  <tr key={r.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px 10px' }}>{r.level}</td>
                    <td style={{ padding: '8px 10px' }}>
                      <div style={{ fontWeight: 700 }}>{r.title}</div>
                      {r.description && <div style={{ fontSize: 12, color: 'var(--text-2)' }}>{r.description}</div>}
                    </td>
                    <td style={{ padding: '8px 10px', fontSize: 12 }}>{r.req_type}{r.research_item_type ? ` · ${r.research_item_type}` : ''}</td>
                    <td style={{ padding: '8px 10px' }}>{r.target_value} {r.unit}</td>
                    <td style={{ padding: '8px 10px' }}>{r.required ? 'Yes' : 'Optional'}</td>
                    <td style={{ padding: '8px 10px' }}>
                      {isAdmin && <button onClick={() => archive(r.id)} style={btnGhost}>Remove</button>}
                    </td>
                  </tr>
                ))}
                {!requirements?.length && (
                  <tr><td colSpan={6} style={{ padding: 16, color: 'var(--text-2)' }}>No requirements yet.</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>

        {!isAdmin ? (
          <aside style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 14, background: 'var(--surface-panel)', height: 'fit-content', fontSize: 14 }}>
            Students see these on their home page and journey. A platform admin adds and changes them; ask the graduate office or an admin if your programme’s rules are missing.
          </aside>
        ) : (
        <aside style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 14, background: 'var(--surface-panel)', height: 'fit-content' }}>
          <h3 style={{ margin: '0 0 6px', fontSize: 15, color: 'var(--text-heading)' }}>Add requirement</h3>
          <div style={{ fontSize: 12, color: 'var(--text-2)', marginBottom: 6 }}>Start from a common kind (fills the form; set your programme’s numbers before adding):</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
            {STARTERS.map(s => (
              <button key={s.label} type="button" style={btnGhost}
                onClick={() => setForm(f => ({ ...f, req_type: s.req_type, research_item_type: s.research_item_type, title: s.title, unit: s.unit, target_value: '1' }))}>
                {s.label}
              </button>
            ))}
          </div>
          <div style={{ display: 'grid', gap: 8 }}>
            <select value={form.level} onChange={e => setForm(f => ({ ...f, level: e.target.value }))} style={inputStyle}>
              {LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
            <select value={form.req_type} onChange={e => setForm(f => ({ ...f, req_type: e.target.value }))} style={inputStyle}>
              {TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
            <input placeholder="Requirement title *" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} style={inputStyle} />
            <input placeholder="Description" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} style={inputStyle} />
            {form.req_type === 'research_item' && (
              <select aria-label="Counts" value={form.research_item_type} onChange={e => setForm(f => ({ ...f, research_item_type: e.target.value }))} style={inputStyle}>
                {ITEM_TYPES.map(t => <option key={t} value={t}>{t ? `Counts: ${t}s` : 'Counts: all publications'}</option>)}
              </select>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <input type="number" placeholder="Target" value={form.target_value} onChange={e => setForm(f => ({ ...f, target_value: e.target.value }))} style={inputStyle} />
              <input placeholder="Unit" value={form.unit} onChange={e => setForm(f => ({ ...f, unit: e.target.value }))} style={inputStyle} />
            </div>
            <label style={{ fontSize: 13, display: 'flex', gap: 6, alignItems: 'center' }}>
              <input type="checkbox" checked={form.required} onChange={e => setForm(f => ({ ...f, required: e.target.checked }))} />
              Required for graduation
            </label>
            <button onClick={createRequirement} style={btnPrimary}>Add requirement</button>
          </div>
        </aside>
        )}
      </div>
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', fontSize: 14, fontFamily: 'var(--font-mono)',
  background: 'var(--surface-input)', border: '1px solid var(--border)',
  borderRadius: 5, color: 'var(--text)', boxSizing: 'border-box',
}

const btnPrimary: React.CSSProperties = {
  padding: '8px 14px', cursor: 'pointer', fontSize: 14, fontWeight: 700,
  background: 'var(--accent)', border: 'none', borderRadius: 6, color: '#fff',
}

const btnGhost: React.CSSProperties = {
  padding: '6px 10px', cursor: 'pointer', fontSize: 12,
  background: 'transparent', border: '1px solid var(--border)',
  borderRadius: 5, color: 'var(--text-2)',
}
