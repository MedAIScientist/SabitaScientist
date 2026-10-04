import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { supervisionApi, type StudentOverview } from '../../api'

export const WEEK_TEXT: Record<StudentOverview['this_week'], { label: string; color: string }> = {
  not_started: { label: 'No update yet', color: 'var(--text-3)' },
  draft: { label: 'Draft', color: '#f59e0b' },
  submitted: { label: 'Submitted — review', color: 'var(--accent)' },
  reviewed: { label: 'Reviewed', color: '#10b981' },
}

function StudentCard({ s }: { s: StudentOverview }) {
  const navigate = useNavigate()
  const week = WEEK_TEXT[s.this_week]
  const urgent = s.attention >= 3
  return (
    <article className="card" style={{ padding: 14, borderLeft: `4px solid ${urgent ? '#f43f5e' : s.attention > 0 ? '#f59e0b' : '#10b981'}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'baseline' }}>
        <a className="text-link" href={`/students/${s.student_id}`} onClick={e => { e.preventDefault(); navigate(`/students/${s.student_id}`) }} style={{ fontSize: 16 }}>{s.name}</a>
        <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{[s.level, s.lab_name].filter(Boolean).join(' · ')}</span>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '6px 0', fontSize: 13 }}>
        <span style={{ color: week.color, fontWeight: 600 }}>{week.label}</span>
        {s.risk && <span className="chip" style={{ color: s.risk === 'high' ? '#f43f5e' : undefined }}>risk {s.risk}</span>}
        <span style={{ color: 'var(--text-3)' }}>{s.weeks_submitted}/{s.weeks_window} weeks</span>
      </div>
      {s.reasons.length > 0 ? (
        <ul style={{ margin: '4px 0', paddingLeft: 18, fontSize: 13 }}>
          {s.reasons.map(r => <li key={r}>{r}</li>)}
        </ul>
      ) : <p style={{ margin: '4px 0', fontSize: 13, color: '#10b981' }}>On track</p>}
      {s.help_requested && <p style={{ fontSize: 13, margin: '4px 0', fontStyle: 'italic' }}>“{s.help_requested.slice(0, 120)}”</p>}
      <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
        <button className="btn" onClick={() => navigate(`/students/${s.student_id}`)}>Open</button>
        <button className="btn" onClick={() => navigate(`/meeting?student=${s.student_id}`)}>{s.awaiting_review ? 'Review update' : 'Meeting'}</button>
      </div>
    </article>
  )
}

/** Every student at a glance, the ones who need you first, with the reasons in words. */
export function StudentsTracker() {
  const { data: students = [], isLoading } = useQuery({ queryKey: ['students-overview'], queryFn: supervisionApi.studentsOverview })
  if (isLoading) return null
  const needs = students.filter(s => s.attention > 0).length
  return (
    <section aria-label="My students" style={{ marginBottom: 22 }}>
      <h2 className="section-title" style={{ marginBottom: 4 }}>My students <span className="count">{students.length}</span></h2>
      <p style={{ margin: '0 0 10px', fontSize: 14, color: 'var(--text-2)' }}>
        {students.length === 0 ? 'Students appear here once they join your lab.' : needs ? `${needs} need${needs === 1 ? 's' : ''} your attention — they are listed first.` : 'Everyone is on track this week.'}
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
        {students.map(s => <StudentCard key={s.student_id} s={s} />)}
      </div>
    </section>
  )
}
