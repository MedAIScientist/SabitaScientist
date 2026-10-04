import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { supervisionApi } from '../api'
import { WEEK_TEXT } from '../components/professor/StudentsTracker'
import { shortDate } from '../components/student/studentData'

function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="card" style={{ padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>{title}</h2>{action}
      </div>
      {children}
    </section>
  )
}

const Muted = ({ children }: { children: ReactNode }) => <p style={{ color: 'var(--text-3)', margin: '4px 0' }}>{children}</p>

/** Everything about one student for their professor: status, updates, requests, research, degree. */
export function StudentProfilePage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const { data: overview = [] } = useQuery({ queryKey: ['students-overview'], queryFn: supervisionApi.studentsOverview })
  const { data: reports = [] } = useQuery({ queryKey: ['reports', id], queryFn: () => supervisionApi.listReports({ student_id: id }) })
  const { data: followups = [] } = useQuery({ queryKey: ['followups', id], queryFn: () => supervisionApi.listFollowups({ studentId: id }) })
  const { data: items = [] } = useQuery({ queryKey: ['research-items', id], queryFn: () => supervisionApi.researchItems({ student_id: id }) })
  const { data: readiness } = useQuery({ queryKey: ['readiness', id], queryFn: () => supervisionApi.readiness(id) })
  const s = overview.find(o => o.student_id === id)
  const sorted = [...reports].sort((a, b) => b.week_start.localeCompare(a.week_start))
  const open = followups.filter(f => f.status === 'open')
  const closed = followups.filter(f => f.status !== 'open').slice(0, 5)
  const reqs = readiness?.requirements ?? []

  if (!s) return <div style={{ padding: 32 }}>{overview.length ? 'This student is not in a lab you lead.' : 'Loading…'}</div>

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1150, display: 'grid', gap: 14 }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <div>
          <div className="crumbs"><a href="/professor" onClick={e => { e.preventDefault(); navigate('/professor') }}>My students</a></div>
          <h1 style={{ margin: '2px 0 4px', fontSize: 24 }}>{s.name}</h1>
          <div style={{ color: 'var(--text-2)' }}>{[s.level, s.lab_name, s.thesis_title].filter(Boolean).join(' · ') || 'No degree journey yet'}</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" onClick={() => navigate(`/meeting?student=${id}`)}>{s.awaiting_review ? 'Review this week' : 'Open in weekly meeting'}</button>
          <button className="btn" onClick={() => navigate('/requirements')}>Requirements</button>
        </div>
      </header>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', fontSize: 14 }} aria-label="Status">
        <span className="chip" style={{ color: WEEK_TEXT[s.this_week].color }}>{WEEK_TEXT[s.this_week].label}</span>
        <span className="chip">{s.weeks_submitted}/{s.weeks_window} recent weeks submitted</span>
        {s.risk && <span className="chip" style={{ color: s.risk === 'high' ? '#f43f5e' : undefined }}>risk {s.risk}</span>}
        <span className="chip">{s.tasks_open} open tasks{s.tasks_overdue ? `, ${s.tasks_overdue} overdue` : ''}</span>
        <span className="chip">{s.active_papers} papers in progress</span>
      </div>

      {(s.reasons.length > 0 || s.help_requested || s.blocked.length > 0) && (
        <Section title="Needs your attention">
          {s.reasons.length > 0 && <ul style={{ margin: '0 0 6px', paddingLeft: 18 }}>{s.reasons.map(r => <li key={r}>{r}</li>)}</ul>}
          {s.help_requested && <p style={{ margin: '4px 0' }}><b>Asked for help:</b> {s.help_requested}</p>}
          {s.blocked.map(b => <p key={b.title} style={{ margin: '4px 0' }}><b>Blocked:</b> {b.title}{b.blocker ? ` — ${b.blocker}` : ''}</p>)}
        </Section>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(330px, 1fr))', gap: 14 }}>
        <Section title="Weekly updates" action={<span style={{ fontSize: 13, color: 'var(--text-3)' }}>latest first</span>}>
          {sorted.length === 0 ? <Muted>No weekly updates yet.</Muted> : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 10 }}>
              {sorted.slice(0, 6).map(r => (
                <li key={r.id} style={{ borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <b>Week of {shortDate(r.week_start)}</b>
                    <span style={{ color: r.status !== 'submitted' ? '#f59e0b' : r.reviewed_at ? '#10b981' : 'var(--accent)' }}>
                      {r.status !== 'submitted' ? 'draft' : r.reviewed_at ? 'reviewed' : 'to review'}
                    </span>
                  </div>
                  {r.accomplished && <div style={{ fontSize: 13 }}><span style={{ color: 'var(--text-3)' }}>Did:</span> {r.accomplished}</div>}
                  {r.next_focus && <div style={{ fontSize: 13 }}><span style={{ color: 'var(--text-3)' }}>Next:</span> {r.next_focus}</div>}
                  {r.feedback && <div style={{ fontSize: 13 }}><span style={{ color: 'var(--text-3)' }}>Your feedback:</span> {r.feedback}</div>}
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Follow-ups you asked for">
          {open.length === 0 && closed.length === 0 && <Muted>No follow-ups yet. Add them when you review an update.</Muted>}
          {open.map(f => (
            <p key={f.id} style={{ margin: '4px 0', color: f.overdue ? '#f43f5e' : undefined }}>
              ○ {f.text}{f.due_date ? ` — due ${shortDate(f.due_date)}` : ''}{f.overdue ? ' (overdue)' : ''}
            </p>
          ))}
          {closed.map(f => (
            <p key={f.id} style={{ margin: '4px 0', color: 'var(--text-3)' }}>
              ✓ {f.text}{f.student_note ? <> — <i>“{f.student_note}”</i></> : ''}
            </p>
          ))}
        </Section>

        <Section title="Research">
          {items.length === 0 ? <Muted>No papers, experiments or patents yet.</Muted> : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 6 }}>
              {items.slice(0, 8).map(i => (
                <li key={i.id}>
                  <a className="text-link" href={i.link_path} onClick={e => { e.preventDefault(); navigate(i.link_path) }}>{i.title}</a>
                  <div style={{ fontSize: 13, color: 'var(--text-3)' }}>{i.kind.replace(/_/g, ' ')} · {i.stage || i.status}{i.deadline ? ` · due ${shortDate(i.deadline)}` : ''}</div>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Graduation readiness">
          {!readiness?.level ? <Muted>The student has not set up a degree journey yet.</Muted>
            : reqs.length === 0 ? <Muted>No requirements yet. <a className="text-link" href="/requirements" onClick={e => { e.preventDefault(); navigate('/requirements') }}>Add them</a> for your {readiness.level} students.</Muted>
              : (
                <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 4 }}>
                  {reqs.map(r => (
                    <li key={r.id}>
                      <span style={{ color: r.met ? '#10b981' : 'var(--text-3)' }}>{r.met ? '✓' : '○'}</span> {r.title}
                      <span style={{ color: 'var(--text-3)' }}> — {r.current_value}/{r.target_value}{r.unit ? ` ${r.unit}` : ''}</span>
                    </li>
                  ))}
                </ul>
              )}
        </Section>
      </div>
    </div>
  )
}
