import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { supervisionApi, api } from '../api'
import { useAuth } from '../auth'
import { GroupAgenda, StudentMeetingBrief } from '../components/supervision/MeetingBrief'
import { SkillsCheck } from '../components/supervision/SkillsCheck'

function currentWeekStart(): string {
  const d = new Date()
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  return new Date(d.setDate(diff)).toISOString().slice(0, 10)
}

export function WeeklyMeetingPage() {
  const { role, isAdmin } = useAuth()
  const qc = useQueryClient()
  const [week, setWeek] = useState(currentWeekStart())
  const [selected, setSelected] = useState<string | null>(
    // Arriving from a brief's link (/meeting?student=<id>) opens that student.
    () => new URLSearchParams(window.location.search).get('student'),
  )
  const [msg, setMsg] = useState<string | null>(null)
  const canRun = role === 'professor' || isAdmin

  const { data: students } = useQuery({
    queryKey: ['my-students'],
    queryFn: () => supervisionApi.myStudents(),
    enabled: canRun,
  })

  const studentIds = students?.map(s => s.student_id) || []

  const { data: users } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.listUsers(),
    enabled: canRun,
  })

  const nameOf = (id: string) => users?.find(u => u.id === id)?.username || id

  const { data: report } = useQuery({
    queryKey: ['meeting-report', week, selected],
    queryFn: () => supervisionApi.listReports({ student_id: selected!, date_from: week, date_to: week }).then(r => r[0] || null),
    enabled: canRun && !!selected,
  })

  const { data: attendance } = useQuery({
    queryKey: ['attendance', week, selected],
    queryFn: () => supervisionApi.getAttendance(selected!, week),
    enabled: canRun && !!selected,
  })

  const [attForm, setAttForm] = useState({ status: 'not_set', joined_mode: '', note: '' })
  const [extForm, setExtForm] = useState({ new_deadline: '', reason: '' })
  const [reviewForm, setReviewForm] = useState({ review_status: 'reviewed', feedback: '', risk_override: '' })

  async function saveAttendance() {
    if (!selected) return
    try {
      await supervisionApi.recordAttendance(selected, week, {
        status: attForm.status,
        joined_mode: attForm.joined_mode || undefined,
        note: attForm.note || undefined,
      })
      setMsg('Attendance recorded.')
      await qc.invalidateQueries({ queryKey: ['attendance', week, selected] })
    } catch (e: any) {
      setMsg(e.message)
    }
  }

  async function saveExtension() {
    if (!selected || !extForm.new_deadline) return
    try {
      await supervisionApi.grantExtension(selected, week, {
        new_deadline: extForm.new_deadline,
        reason: extForm.reason || undefined,
      })
      setMsg('Extension granted.')
      setExtForm({ new_deadline: '', reason: '' })
    } catch (e: any) {
      setMsg(e.message)
    }
  }

  async function saveReview() {
    if (!report) return
    try {
      await supervisionApi.reviewReport(report.id, {
        review_status: reviewForm.review_status,
        feedback: reviewForm.feedback || undefined,
        risk_override: reviewForm.risk_override || undefined,
      })
      setMsg('Review saved.')
      await qc.invalidateQueries({ queryKey: ['meeting-report', week, selected] })
    } catch (e: any) {
      setMsg(e.message)
    }
  }

  if (!canRun) return <div style={{ padding: 32 }}>Weekly meeting is for professors.</div>

  return (
    <div style={{ padding: '24px 32px', display: 'grid', gridTemplateColumns: '280px 1fr', gap: 22, maxWidth: 1200 }}>
      <aside>
        <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', color: 'var(--text-dim)' }}>Weekly meeting</div>
        <h1 style={{ fontSize: 17, margin: '4px 0 12px', color: 'var(--text-heading)' }}>Week of {week}</h1>
        <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
          <button onClick={() => {
            const d = new Date(week); d.setDate(d.getDate() - 7); setWeek(d.toISOString().slice(0, 10))
          }} style={btnGhost}>← Prev</button>
          <button onClick={() => {
            const d = new Date(week); d.setDate(d.getDate() + 7); setWeek(d.toISOString().slice(0, 10))
          }} style={btnGhost}>Next →</button>
        </div>
        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-dim)', marginBottom: 8 }}>Students</div>
        {(studentIds.length === 0) && (
          <div style={{ fontSize: 13, color: 'var(--text-2)', padding: 10, border: '1px dashed var(--border)', borderRadius: 6 }}>
            No students assigned yet. Ask an admin to assign supervisors.
          </div>
        )}
        {studentIds.map(id => (
          <button
            key={id}
            onClick={() => setSelected(id)}
            style={{
              display: 'block', width: '100%', textAlign: 'left', marginBottom: 6,
              padding: '10px 12px', cursor: 'pointer', borderRadius: 6,
              background: selected === id ? 'rgba(var(--accent-rgb),0.14)' : 'var(--surface-panel)',
              border: selected === id ? '1px solid rgba(var(--accent-rgb),0.4)' : '1px solid var(--border)',
              color: 'var(--text)',
            }}
          >
            <div style={{ fontWeight: 700, fontSize: 14 }}>{nameOf(id)}</div>
            <div style={{ fontSize: 12, color: 'var(--text-2)' }}>
              {report && selected === id ? `Report: ${report.status}` : 'Open to review'}
            </div>
          </button>
        ))}
      </aside>

      <main>
        {msg && <div style={{ padding: '8px 12px', marginBottom: 14, borderRadius: 6, background: 'rgba(var(--accent-rgb),0.12)', border: '1px solid rgba(var(--accent-rgb),0.3)', fontSize: 14 }}>{msg}</div>}

        {!selected ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {studentIds.length > 0 && <GroupAgenda />}
            <div style={{ padding: 24, color: 'var(--text-2)', border: '1px dashed var(--border)', borderRadius: 8 }}>
              Select a student to review their weekly report, record attendance, and capture follow-ups.
            </div>
          </div>
        ) : (
          <>
            <h2 style={{ fontSize: 15, margin: '0 0 8px', color: 'var(--text-heading)' }}>{nameOf(selected)}</h2>
            <div style={{ marginBottom: 16 }}><StudentMeetingBrief studentId={selected} /></div>
            <div style={{ marginBottom: 16 }}><SkillsCheck studentId={selected} perspective="supervisor" /></div>

            {!report || report.status === 'draft' ? (
              <div style={{ padding: 14, marginBottom: 16, borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-panel)', fontSize: 14, color: 'var(--text-2)' }}>
                No submitted report for this week. You can still record attendance and grant an extension.
              </div>
            ) : (
              <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 16, marginBottom: 16, background: 'var(--surface-panel)' }}>
                <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
                  <Chip label={report.status} />
                  <Chip label={`risk: ${report.risk_override || report.risk_level}`} />
                  <Chip label={report.review_status} />
                </div>
                {report.accomplished && <p><strong>Accomplished:</strong> {report.accomplished}</p>}
                {report.next_focus && <p><strong>Next focus:</strong> {report.next_focus}</p>}
                {report.support_requested && <p><strong>Support requested:</strong> {report.support_requested}</p>}
                {report.items.map(item => (
                  <div key={item.id} style={{ borderTop: '1px solid var(--border)', paddingTop: 10, marginTop: 10, fontSize: 13 }}>
                    <div style={{ fontWeight: 700 }}>{item.item_title} · {item.progress_pct}% · {item.status}</div>
                    {item.what_changed && <div style={{ color: 'var(--text-2)' }}>Changed: {item.what_changed}</div>}
                    {item.next_step && <div style={{ color: 'var(--text-2)' }}>Next: {item.next_step}</div>}
                    {item.needs_help && <div style={{ color: 'var(--accent)' }}>Needs help{item.blocker ? ` — ${item.blocker}` : ''}</div>}
                  </div>
                ))}
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <section style={panelStyle}>
                <h3 style={h3Style}>Attendance</h3>
                <div style={{ display: 'grid', gap: 8 }}>
                  <select value={attForm.status} onChange={e => setAttForm(f => ({ ...f, status: e.target.value }))} style={inputStyle}>
                    {['not_set', 'on_time', 'late', 'excused', 'absent'].map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                  <select value={attForm.joined_mode} onChange={e => setAttForm(f => ({ ...f, joined_mode: e.target.value }))} style={inputStyle}>
                    <option value="">Joined mode…</option>
                    <option value="in_person">In person</option>
                    <option value="online">Online</option>
                  </select>
                  <textarea placeholder="Meeting note" value={attForm.note} onChange={e => setAttForm(f => ({ ...f, note: e.target.value }))} style={{ ...inputStyle, minHeight: 60 }} />
                  <button onClick={saveAttendance} style={btnPrimary}>Record attendance</button>
                </div>
              </section>

              <section style={panelStyle}>
                <h3 style={h3Style}>Supervisor review</h3>
                <div style={{ display: 'grid', gap: 8 }}>
                  <select value={reviewForm.review_status} onChange={e => setReviewForm(f => ({ ...f, review_status: e.target.value }))} style={inputStyle}>
                    {['pending', 'needs_review', 'reviewed', 'changes_requested', 'closed'].map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                  <select value={reviewForm.risk_override} onChange={e => setReviewForm(f => ({ ...f, risk_override: e.target.value }))} style={inputStyle}>
                    <option value="">Risk override…</option>
                    {['low', 'medium', 'high', 'critical'].map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                  <textarea placeholder="Feedback" value={reviewForm.feedback} onChange={e => setReviewForm(f => ({ ...f, feedback: e.target.value }))} style={{ ...inputStyle, minHeight: 60 }} />
                  <button onClick={saveReview} style={btnPrimary}>Save review</button>
                </div>
              </section>

              <section style={panelStyle}>
                <h3 style={h3Style}>Late-submission extension</h3>
                <div style={{ display: 'grid', gap: 8 }}>
                  <input type="datetime-local" value={extForm.new_deadline} onChange={e => setExtForm(f => ({ ...f, new_deadline: e.target.value }))} style={inputStyle} />
                  <input placeholder="Reason (optional)" value={extForm.reason} onChange={e => setExtForm(f => ({ ...f, reason: e.target.value }))} style={inputStyle} />
                  <button onClick={saveExtension} style={btnPrimary}>Grant extension</button>
                </div>
              </section>
            </div>
          </>
        )}
      </main>
    </div>
  )
}

function Chip({ label }: { label: string }) {
  return (
    <span style={{
      fontSize: 11, fontFamily: 'var(--font-mono)', padding: '2px 8px',
      borderRadius: 999, background: 'var(--surface-input)', border: '1px solid var(--border)',
      color: 'var(--text-2)',
    }}>{label}</span>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', fontSize: 14, fontFamily: 'var(--font-mono)',
  background: 'var(--surface-input)', border: '1px solid var(--border)',
  borderRadius: 5, color: 'var(--text)', boxSizing: 'border-box',
}

const panelStyle: React.CSSProperties = {
  border: '1px solid var(--border)', borderRadius: 8, padding: 14, background: 'var(--surface-panel)',
}

const h3Style: React.CSSProperties = { margin: '0 0 10px', fontSize: 15, color: 'var(--text-heading)' }

const btnPrimary: React.CSSProperties = {
  padding: '8px 14px', cursor: 'pointer', fontSize: 14, fontWeight: 700,
  background: 'var(--accent)', border: 'none', borderRadius: 6, color: '#fff',
}

const btnGhost: React.CSSProperties = {
  padding: '6px 10px', cursor: 'pointer', fontSize: 13,
  background: 'transparent', border: '1px solid var(--border)',
  borderRadius: 5, color: 'var(--text-2)',
}
