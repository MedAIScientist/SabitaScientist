import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CohortRow, supervisionApi } from '../../api'

function terms(today = new Date()): string[] {
  const y = today.getFullYear(), m = today.getMonth() + 1
  let year = m >= 9 ? y : m === 1 ? y - 1 : y
  let season = m >= 9 || m === 1 ? 'Fall' : 'Spring'
  const out = []
  for (let i = 0; i < 4; i++) {
    out.push(`${year} ${season}`)
    if (season === 'Fall') season = 'Spring'
    else { season = 'Fall'; year -= 1 }
  }
  return out
}

const pct = (v: number | null) => (v === null ? '—' : `${Math.round(v * 100)}%`)
const num = (v: number | null) => (v === null ? '—' : String(v))

/**
 * The supervisor's students side by side for a term. Cells that stand out against
 * the group median are tinted — red for clearly behind, amber for worth a look.
 */
export function CohortView() {
  const options = terms()
  const [term, setTerm] = useState(options[0])
  const { data } = useQuery({ queryKey: ['cohort', term], queryFn: () => supervisionApi.cohort(term) })
  if (!data || data.rows.length === 0) return null
  const m = data.medians

  const tone = (r: CohortRow, key: keyof CohortRow): string | undefined => {
    const v = r[key] as number | null
    if (v === null) return undefined
    if (key === 'submission_rate' && m.submission_rate !== null && v < 0.75 * (m.submission_rate as number)) return 'var(--rose)'
    if (key === 'followups_overdue' && v > 0) return 'var(--rose)'
    if ((key === 'followups_open' || key === 'high_risk_weeks') && m[key] !== null && v > (m[key] as number)) return 'var(--amber)'
    return undefined
  }
  const cell = (r: CohortRow, key: keyof CohortRow, text: string) => {
    const c = tone(r, key)
    return <td style={c ? { color: c, fontWeight: 600 } : undefined}>{text}</td>
  }

  return (
    <section className="card" style={{ marginBottom: 22 }} aria-label="Cohort">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 10 }}>
        <div>
          <div className="request-title">Cohort · {data.term}</div>
          <div className="request-meta">Your students side by side, from recorded updates, follow-ups, papers and skills checks.</div>
        </div>
        <select className="input" style={{ width: 140 }} value={term} onChange={e => setTerm(e.target.value)} aria-label="Term">
          {options.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table className="bucket-table">
          <thead>
            <tr>
              <th>Student</th><th>Weekly updates</th><th>Follow-ups done / asked</th><th>Open</th><th>Overdue</th>
              <th>Days to close</th><th>High-risk weeks</th><th>Papers submitted</th><th>Skills (self / supervisor)</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map(r => (
              <tr key={r.student_id}>
                <td><Link to={`/meeting?student=${r.student_id}`}>{r.name}</Link></td>
                {cell(r, 'submission_rate', `${r.weeks_submitted}/${r.weeks_elapsed} · ${pct(r.submission_rate)}`)}
                <td>{r.followups_done} / {r.followups_asked}</td>
                {cell(r, 'followups_open', String(r.followups_open))}
                {cell(r, 'followups_overdue', String(r.followups_overdue))}
                <td>{num(r.median_days_to_close)}</td>
                {cell(r, 'high_risk_weeks', String(r.high_risk_weeks))}
                <td>{r.papers_submitted}</td>
                <td>{num(r.skills_self)} / {num(r.skills_supervisor)}</td>
              </tr>
            ))}
            <tr className="hint">
              <td>Group median</td><td>{pct(m.submission_rate)}</td><td /><td>{num(m.followups_open)}</td><td />
              <td>{num(m.median_days_to_close)}</td><td>{num(m.high_risk_weeks)}</td><td>{num(m.papers_submitted)}</td><td />
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  )
}
