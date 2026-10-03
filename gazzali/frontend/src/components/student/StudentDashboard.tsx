import { useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api, supervisionApi, type TaskStatus, type WeeklyTask } from '../../api'
import { ResearchGatesInbox } from '../experiment/ResearchGatesInbox'
import {
  type Tone, attention, currentReport, dueText, latestProgress, meetingText, shortDate, thisMonday, upcoming, weekState, weeklyHistory,
} from './studentData'

const TONE: Record<Tone, string> = { neutral: 'var(--text-2)', good: '#10b981', warn: '#f59e0b', bad: '#f43f5e' }

function Card({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="card" style={{ padding: 18 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

function Stat({ label, value, detail, tone = 'neutral', onClick }: { label: string; value: ReactNode; detail: string; tone?: Tone; onClick: () => void }) {
  return (
    <button className="card" onClick={onClick} style={{ textAlign: 'left', padding: 16, cursor: 'pointer', color: 'var(--text)' }}>
      <div style={{ fontSize: 13, color: 'var(--text-3)' }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 700, margin: '4px 0', color: tone === 'neutral' ? 'var(--text-heading)' : TONE[tone] }}>{value}</div>
      <div style={{ fontSize: 13, color: 'var(--text-3)' }}>{detail}</div>
    </button>
  )
}

const Empty = ({ children }: { children: ReactNode }) => <p style={{ color: 'var(--text-3)', margin: '6px 0' }}>{children}</p>

/**
 * A student's week at a glance: what to do now, what is due, how research and the
 * degree are progressing. Every block links to the page where the work happens.
 */
export function StudentDashboard({ username }: { username: string | null }) {
  const navigate = useNavigate()
  const monday = thisMonday()
  const { data: reports = [] } = useQuery({ queryKey: ['my-reports'], queryFn: () => supervisionApi.listReports() })
  const { data: tasks = [] } = useQuery({ queryKey: ['my-tasks'], queryFn: api.myTasks })
  const { data: followups = [] } = useQuery({ queryKey: ['my-followups'], queryFn: () => supervisionApi.listFollowups({ status: 'open' }) })
  const { data: items = [] } = useQuery({ queryKey: ['my-research-items'], queryFn: () => supervisionApi.researchItems() })
  const { data: supervisor } = useQuery({ queryKey: ['my-supervisor'], queryFn: supervisionApi.mySupervisor })
  const { data: meeting } = useQuery({
    queryKey: ['meeting', supervisor?.professor_id], enabled: !!supervisor?.professor_id,
    queryFn: () => supervisionApi.getMeetingSetting(monday, supervisor!.professor_id),
  })
  const { data: readiness } = useQuery({ queryKey: ['my-readiness'], queryFn: () => supervisionApi.readiness() })

  const report = currentReport(reports, monday)
  const week = weekState(report)
  const urgent = attention(tasks, followups, report)
  const soon = upcoming(tasks, items, followups)
  const progress = latestProgress(reports)
  const history = weeklyHistory(reports)
  const overdueTasks = tasks.filter(t => dueText(t.deadline).tone === 'bad').length
  const overdueRequests = followups.filter(f => f.overdue).length
  const active = items.filter(i => !['done', 'published', 'accepted', 'archived'].includes(i.status))
  const meet = meetingText(meeting)
  const reqs = readiness?.requirements ?? []

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ margin: '0 0 4px', fontSize: 24, color: 'var(--text-heading)' }}>Welcome, {username}</h1>
          <p style={{ margin: 0, color: 'var(--text-2)' }}>
            {supervisor ? <>Supervisor: <b>{supervisor.professor_name ?? 'your supervisor'}</b>{meet && <> · weekly meeting {meet}</>}</>
              : <>You are not in a lab yet. <a className="text-link" href="/labs" onClick={e => { e.preventDefault(); navigate('/labs') }}>Ask to join your supervisor’s lab</a> so they can follow your work.</>}
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/weekly-update')}>{week.cta}</button>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }} aria-label="Overview">
        <Stat label="This week’s update" value={week.label} detail={week.detail} tone={week.tone} onClick={() => navigate('/weekly-update')} />
        <Stat label="Open tasks" value={tasks.length} detail={overdueTasks ? `${overdueTasks} overdue` : 'none overdue'} tone={overdueTasks ? 'bad' : 'neutral'} onClick={() => navigate('/projects')} />
        <Stat label="Supervisor requests" value={followups.length} detail={overdueRequests ? `${overdueRequests} overdue` : 'open follow-ups'} tone={overdueRequests ? 'bad' : 'neutral'} onClick={() => navigate('/weekly-update')} />
        <Stat label="Graduation readiness" value={readiness?.level && reqs.length ? `${Math.round(readiness.readiness_pct)}%` : '—'}
          detail={!readiness?.level ? 'set up your journey' : reqs.length ? `${reqs.filter(r => r.met).length}/${reqs.length} requirements met` : 'no requirements set yet'} onClick={() => navigate('/journey')} />
      </div>

      {urgent.length > 0 && (
        <Card title="Needs your attention">
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 6 }}>
            {urgent.map(a => (
              <li key={a.key}>
                <a href={a.path} onClick={e => { e.preventDefault(); navigate(a.path) }}
                  style={{ display: 'block', padding: '8px 10px', borderLeft: `3px solid ${TONE[a.tone]}`, borderRadius: 4, background: 'var(--surface-2)', color: 'var(--text)', textDecoration: 'none' }}>
                  <b>{a.text}</b><div style={{ fontSize: 13, color: 'var(--text-3)' }}>{a.detail}</div>
                </a>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <ResearchGatesInbox />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <Card title="My active research" action={<a className="text-link" href="/research-items" onClick={e => { e.preventDefault(); navigate('/research-items') }}>View all</a>}>
          {active.length === 0 ? <Empty>Nothing in progress. Your papers, experiments and patents appear here.</Empty> : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 12 }}>
              {active.slice(0, 6).map(i => {
                const pct = progress.get(i.id) ?? progress.get(i.title.toLowerCase())
                return (
                  <li key={i.id}>
                    <a href={i.link_path} onClick={e => { e.preventDefault(); navigate(i.link_path) }} style={{ color: 'var(--text)', textDecoration: 'none' }}>
                      <div style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--accent)' }}>{i.kind.replace(/_/g, ' ')}</div>
                      <div style={{ fontWeight: 600 }}>{i.title}</div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: 'var(--text-3)' }}>
                        <span>{i.stage || i.status}{i.deadline ? ` · ${dueText(i.deadline).text}` : ''}</span>
                        {pct != null && <span>{pct}%</span>}
                      </div>
                      {pct != null && (
                        <div style={{ height: 5, background: 'var(--border)', borderRadius: 3, marginTop: 4 }}>
                          <div style={{ width: `${Math.min(100, pct)}%`, height: 5, borderRadius: 3, background: 'var(--accent)' }} />
                        </div>
                      )}
                    </a>
                  </li>
                )
              })}
            </ul>
          )}
        </Card>

        <Card
          title="My tasks this week"
          action={
            <a href="/weekly-update" onClick={e => { e.preventDefault(); navigate('/weekly-update') }} style={{ fontSize: 13 }}>
              Weekly update →
            </a>
          }
        >
          <TaskWeek weekStart={monday} />
        </Card>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <Card title="Next 30 days">
          {soon.length === 0 ? <Empty>No deadlines in the next 30 days.</Empty> : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 6 }}>
              {soon.slice(0, 8).map((u, n) => (
                <li key={`${u.date}-${n}`} style={{ display: 'flex', gap: 12 }}>
                  <span style={{ minWidth: 92, fontWeight: 600, color: 'var(--accent)' }}>{shortDate(u.date)}</span>
                  <a className="plain-link" href={u.path} onClick={e => { e.preventDefault(); navigate(u.path) }}>
                    <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{u.kind}</span><br /><span className="plain-link-title">{u.title}</span>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Weekly updates" action={<a className="text-link" href="/weekly-update" onClick={e => { e.preventDefault(); navigate('/weekly-update') }}>History</a>}>
          <div style={{ display: 'flex', gap: 6, alignItems: 'flex-end' }} aria-label="Last 8 weeks">
            {history.map(h => (
              <div key={h.week} title={`${h.week}: ${h.status}`} style={{ flex: 1, textAlign: 'center' }}>
                <div style={{ height: 34, borderRadius: 4, background: h.status === 'submitted' ? '#10b981' : h.status === 'draft' ? '#f59e0b' : 'var(--border)' }} />
                <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 3 }}>{shortDate(h.week, false)}</div>
              </div>
            ))}
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-3)', margin: '8px 0 0' }}>
            {history.filter(h => h.status === 'submitted').length} of the last {history.length} weeks submitted. Green: submitted · amber: draft only · grey: none.
          </p>
        </Card>
      </div>

      <Card title="Graduation readiness" action={<a className="text-link" href="/journey" onClick={e => { e.preventDefault(); navigate('/journey') }}>Open journey</a>}>
        {!readiness?.level ? <Empty>Add your degree on <a className="text-link" href="/journey" onClick={e => { e.preventDefault(); navigate('/journey') }}>My journey</a> to see what you still need.</Empty> : (
          <>
            <div style={{ fontSize: 14, marginBottom: 8 }}>{readiness.level.toUpperCase()}{readiness.thesis_title ? ` · ${readiness.thesis_title}` : ''}</div>
            {reqs.length === 0 && <Empty>Your programme’s graduation requirements have not been set up yet. Ask your supervisor or the graduate office.</Empty>}
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 4 }}>
              {reqs.map(r => (
                <li key={r.id} style={{ fontSize: 14 }}>
                  <span style={{ color: r.met ? '#10b981' : 'var(--text-3)' }}>{r.met ? '✓' : '○'}</span> {r.title}
                  <span style={{ color: 'var(--text-3)' }}> — {r.current_value}/{r.target_value}{r.unit ? ` ${r.unit}` : ''}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>
    </div>
  )
}

const TASK_STATUSES: { value: TaskStatus; label: string }[] = [
  { value: 'todo', label: 'To do' },
  { value: 'in_progress', label: 'Doing' },
  { value: 'done', label: 'Done' },
]

/**
 * The week's assigned tasks, and the place to move them.
 *
 * A task and its line in the weekly update are one piece of work seen from two
 * sides, so moving the task here writes the update line in the same action — the
 * student should not have to say the same thing twice. What the update says
 * *about* the work (what changed, blockers) stays on the weekly page, because that
 * is writing, not tracking.
 */
function TaskWeek({ weekStart }: { weekStart: string }) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [notice, setNotice] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['weekly-tasks', weekStart],
    queryFn: () => supervisionApi.weeklyTasks(weekStart),
  })

  const move = useMutation({
    mutationFn: (vars: { taskId: string; status?: TaskStatus; needsHelp?: boolean }) =>
      supervisionApi.updateWeeklyTask(
        vars.taskId,
        {
          ...(vars.status ? { status: vars.status } : {}),
          ...(vars.needsHelp !== undefined ? { needs_help: vars.needsHelp } : {}),
        },
        weekStart,
      ),
    onSuccess: result => {
      setNotice(
        result.report_locked
          ? 'Task moved. This week’s report was already submitted, so it stays as your supervisor read it.'
          : null,
      )
      for (const key of [['weekly-tasks', weekStart], ['my-tasks'], ['weekly-report', weekStart]]) {
        qc.invalidateQueries({ queryKey: key })
      }
    },
    onError: (e: Error) => setNotice(e.message || 'Could not update the task'),
  })

  const tasks = data?.tasks ?? []
  const locked = data?.report_status === 'submitted'

  if (isLoading) return <Empty>Loading your tasks…</Empty>
  if (tasks.length === 0) {
    return <Empty>No tasks assigned to you this week. Tasks assigned on a project board appear here.</Empty>
  }

  return (
    <>
      {notice && (
        <p style={{ fontSize: 13, color: 'var(--text-2)', margin: '0 0 10px' }} role="status">{notice}</p>
      )}
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 10 }}>
        {tasks.slice(0, 8).map(t => {
          const d = dueText(t.deadline)
          const doing = move.isPending && move.variables?.taskId === t.id
          return (
            <li key={t.id} style={{ opacity: doing ? 0.6 : 1 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'baseline' }}>
                <a
                  href={`/projects/${t.project_id}`}
                  onClick={e => { e.preventDefault(); navigate(`/projects/${t.project_id}`) }}
                  style={{ color: 'var(--text)', textDecoration: 'none', fontWeight: 600 }}
                >
                  {t.title}
                </a>
                {t.item_id && (
                  <span title="Listed in this week’s update" style={{ fontSize: 12, color: '#10b981', whiteSpace: 'nowrap' }}>
                    ✓ in update
                  </span>
                )}
              </div>
              <div style={{ fontSize: 13, marginBottom: 6 }}>
                <span style={{ color: 'var(--text-3)' }}>{t.project_name} · </span>
                <span style={{ color: TONE[d.tone] }}>{d.text}</span>
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                {TASK_STATUSES.map(s => {
                  const active = t.status === s.value
                  return (
                    <button
                      key={s.value}
                      className={active ? 'btn btn-primary' : 'btn'}
                      aria-pressed={active}
                      disabled={doing}
                      onClick={() => move.mutate({ taskId: t.id, status: s.value })}
                      style={{ fontSize: 12, padding: '3px 10px' }}
                    >
                      {s.label}
                    </button>
                  )
                })}
                <button
                  className="btn"
                  disabled={doing || locked}
                  title={locked ? 'The week’s report is submitted; only the task can move now' : 'Flag this in your weekly update'}
                  onClick={() => move.mutate({ taskId: t.id, needsHelp: !t.item_needs_help })}
                  style={{ fontSize: 12, padding: '3px 10px', color: t.item_needs_help ? '#f59e0b' : undefined }}
                >
                  {t.item_needs_help ? '⚠ needs help' : 'Needs help?'}
                </button>
              </div>
            </li>
          )
        })}
      </ul>
      {tasks.length > 8 && (
        <p style={{ fontSize: 13, color: 'var(--text-3)', margin: '8px 0 0' }}>
          {tasks.length - 8} more — see <a href="/weekly-update" onClick={e => { e.preventDefault(); navigate('/weekly-update') }}>the full week</a>.
        </p>
      )}
    </>
  )
}
