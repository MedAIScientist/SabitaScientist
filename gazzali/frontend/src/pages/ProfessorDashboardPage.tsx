import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { supervisionApi } from '../api'
import { ApprovalsInbox } from '../components/imaging/ApprovalsInbox'
import { ResearchGatesInbox } from '../components/experiment/ResearchGatesInbox'
import { CohortView } from '../components/supervision/CohortView'
import { StudentsTracker } from '../components/professor/StudentsTracker'
import { JoinRequestsInbox, NoLabPrompt } from '../components/supervision/LabJoin'
import { useAuth } from '../auth'

/** Professor group overview: KPIs, trends, workload, and what needs attention. */
export function ProfessorDashboardPage() {
  const { role, isAdmin } = useAuth()
  const navigate = useNavigate()
  const canView = role === 'professor' || isAdmin

  const { data, isLoading, error } = useQuery({
    queryKey: ['professor-analytics'],
    queryFn: () => supervisionApi.professorAnalytics(),
    enabled: canView,
  })

  if (!canView) return <div style={{ padding: 32 }}>Professor analytics are available to professors and admins.</div>
  if (isLoading) return <div style={{ padding: 32 }}>Loading group overview…</div>
  if (error) return <div style={{ padding: 32, color: '#f43f5e' }}>{(error as Error).message}</div>
  if (!data) return null

  const { kpis, students, weekly_trend, attendance, reports_needing_attention, active_deadlines, work_mix } = data
  const maxTrend = Math.max(1, ...weekly_trend.map(t => t.submitted))
  const attTotal = Object.values(attendance).reduce((a, b) => a + b, 0) || 1

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1200 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', color: 'var(--text-dim)' }}>Group overview</div>
          <h1 style={{ margin: '4px 0 6px', fontSize: 22, color: 'var(--text-heading)' }}>Professor dashboard</h1>
          <p style={{ color: 'var(--text-2)', margin: 0, fontSize: 14 }}>
            Filter the group, spot exceptions, and open the student or report that needs attention.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button onClick={() => navigate('/meeting')} style={btnPrimary}>Weekly meeting</button>
          <button onClick={() => navigate('/supervision/reports')} style={btnGhost}>Review reports</button>
          <button onClick={() => navigate('/journey')} style={btnGhost}>Journeys</button>
        </div>
      </div>

      <NoLabPrompt />
      <JoinRequestsInbox />
      <ApprovalsInbox />
      <ResearchGatesInbox />
      <StudentsTracker />
      <CohortView />

      {/* KPI cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', gap: 12, marginBottom: 22 }}>
        <Kpi label="Students" value={kpis.student_count} />
        <Kpi label="Submitted this week" value={kpis.submitted_this_week} accent />
        <Kpi label="Needs review" value={kpis.needs_review} warn={kpis.needs_review > 0} />
        <Kpi label="Draft / missing" value={kpis.draft_or_missing} warn={kpis.draft_or_missing > 0} />
        <Kpi label="Help requests" value={kpis.help_requests} warn={kpis.help_requests > 0} />
        <Kpi label="High risk" value={kpis.high_risk} warn={kpis.high_risk > 0} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 16, marginBottom: 18 }}>
        {/* Weekly trend */}
        <section style={panel}>
          <h2 style={h2}>Weekly reporting trend</h2>
          <p style={sub}>Submitted reports in the latest weeks (on-time in orange)</p>
          {weekly_trend.length === 0 ? (
            <Empty text="No submissions yet." />
          ) : (
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 120, marginTop: 12 }}>
              {weekly_trend.map(t => (
                <div key={t.week} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-2)', fontFamily: 'var(--font-mono)' }}>{t.submitted}</div>
                  <div style={{
                    width: '100%', borderRadius: '4px 4px 0 0',
                    height: Math.max(4, (t.submitted / maxTrend) * 80),
                    background: t.on_time > 0 ? 'var(--accent)' : 'var(--border)',
                  }} />
                  <div style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                    {t.week.slice(5)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Attendance */}
        <section style={panel}>
          <h2 style={h2}>Meeting attendance</h2>
          <p style={sub}>Recorded status in the selected period</p>
          {attTotal === 1 && Object.keys(attendance).length === 0 ? (
            <Empty text="No attendance recorded yet." />
          ) : (
            <div style={{ marginTop: 12, display: 'grid', gap: 8 }}>
              {Object.entries(attendance).map(([status, count]) => (
                <div key={status}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 3 }}>
                    <span>{status}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>{count}</span>
                  </div>
                  <div style={{ height: 8, background: 'var(--surface-input)', borderRadius: 4, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${(count / attTotal) * 100}%`, background: 'var(--accent)', borderRadius: 4 }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Workload by student */}
      <section style={{ ...panel, marginBottom: 18 }}>
        <h2 style={h2}>Review and follow-up workload</h2>
        <p style={sub}>Open reviews, help signals, and latest report per student</p>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr>
                {['Student', 'Open reviews', 'Help requests', 'Latest report', 'Attendance', ''].map(h => (
                  <th key={h} style={th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {students.map(s => (
                <tr key={s.student_id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={td}><strong>{s.username}</strong></td>
                  <td style={td}>{s.open_reviews}</td>
                  <td style={{ ...td, color: s.help_requests ? 'var(--accent)' : undefined }}>{s.help_requests}</td>
                  <td style={td}>{s.latest_week ? `${s.latest_week} · ${s.latest_status}` : '—'}</td>
                  <td style={td}>{s.last_attendance || '—'}</td>
                  <td style={td}>
                    <button onClick={() => navigate(`/meeting`)} style={btnGhost}>Meeting</button>
                  </td>
                </tr>
              ))}
              {!students.length && (
                <tr><td colSpan={6} style={{ ...td, color: 'var(--text-2)' }}>No students assigned.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: 16 }}>
        {/* Attention list */}
        <section style={panel}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ ...h2, marginBottom: 0 }}>Reports requiring attention</h2>
            <button onClick={() => navigate('/supervision/reports')} style={btnGhost}>All reports</button>
          </div>
          <p style={sub}>Submitted updates still open for review</p>
          {reports_needing_attention.length === 0 ? (
            <Empty text="Nothing waiting — inbox zero." />
          ) : (
            <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
              {reports_needing_attention.map(r => (
                <button
                  key={r.report_id}
                  onClick={() => navigate('/supervision/reports')}
                  style={{
                    textAlign: 'left', padding: '10px 12px', cursor: 'pointer',
                    background: 'var(--surface-input)', border: '1px solid var(--border)',
                    borderRadius: 6, color: 'var(--text)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <strong>{r.username}</strong>
                    <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>{r.week_start}</span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 4 }}>
                    {r.review_status} · risk: {r.risk}
                    {r.support_requested ? ` · ${r.support_requested}` : ''}
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>

        <div style={{ display: 'grid', gap: 16 }}>
          {/* Deadlines */}
          <section style={panel}>
            <h2 style={h2}>Active deadlines</h2>
            <p style={sub}>Nearest item deadlines across the group</p>
            {active_deadlines.length === 0 ? (
              <Empty text="No upcoming deadlines recorded." />
            ) : (
              <div style={{ display: 'grid', gap: 8 }}>
                {active_deadlines.map((d, i) => (
                  <div key={i} style={{ fontSize: 13, padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 6 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                      <strong style={{ fontSize: 13 }}>{d.item_title}</strong>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-2)' }}>{d.next_deadline?.slice(0, 10)}</span>
                    </div>
                    <div style={{ color: 'var(--text-2)', fontSize: 12, marginTop: 2 }}>
                      {d.username} · {d.progress_pct}% · {d.status || 'open'}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Work mix */}
          <section style={panel}>
            <h2 style={h2}>Work mix</h2>
            <p style={sub}>Item kinds from weekly updates</p>
            {work_mix.length === 0 ? (
              <Empty text="No item updates yet." />
            ) : (
              <div style={{ display: 'grid', gap: 8, marginTop: 8 }}>
                {work_mix.map(m => {
                  const max = Math.max(...work_mix.map(x => x.count), 1)
                  return (
                    <div key={m.kind}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 3 }}>
                        <span>{m.kind}</span>
                        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>{m.count}</span>
                      </div>
                      <div style={{ height: 8, background: 'var(--surface-input)', borderRadius: 4, overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${(m.count / max) * 100}%`, background: 'var(--accent)', borderRadius: 4 }} />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}

function Kpi({ label, value, accent, warn }: { label: string; value: number; accent?: boolean; warn?: boolean }) {
  return (
    <div style={{
      padding: '14px 14px', borderRadius: 8, background: 'var(--surface-panel)',
      border: warn ? '1px solid rgba(var(--accent-rgb),0.45)' : '1px solid var(--border)',
    }}>
      <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', color: 'var(--text-dim)', marginBottom: 6 }}>
        {label.toUpperCase()}
      </div>
      <div style={{
        fontSize: 24, fontWeight: 700, fontFamily: 'var(--font-mono)',
        color: accent || warn ? 'var(--accent)' : 'var(--text-heading)',
      }}>{value}</div>
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return <div style={{ padding: '14px 0', color: 'var(--text-2)', fontSize: 13 }}>{text}</div>
}

const panel: React.CSSProperties = {
  border: '1px solid var(--border)', borderRadius: 8, padding: 16, background: 'var(--surface-panel)',
}
const h2: React.CSSProperties = { margin: '0 0 4px', fontSize: 16, color: 'var(--text-heading)' }
const sub: React.CSSProperties = { margin: '0 0 10px', fontSize: 12, color: 'var(--text-2)' }
const th: React.CSSProperties = {
  textAlign: 'left', padding: '8px 10px', borderBottom: '1px solid var(--border)',
  color: 'var(--text-dim)', fontSize: 11, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em',
}
const td: React.CSSProperties = { padding: '8px 10px', fontSize: 13 }
const btnPrimary: React.CSSProperties = {
  padding: '8px 14px', cursor: 'pointer', fontSize: 13, fontWeight: 700,
  background: 'var(--accent)', border: 'none', borderRadius: 6, color: '#fff',
}
const btnGhost: React.CSSProperties = {
  padding: '6px 12px', cursor: 'pointer', fontSize: 12,
  background: 'transparent', border: '1px solid var(--border)',
  borderRadius: 5, color: 'var(--text-2)',
}
