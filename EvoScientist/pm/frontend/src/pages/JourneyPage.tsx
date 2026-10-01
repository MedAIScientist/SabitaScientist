import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { supervisionApi, api } from '../api'
import { useAuth } from '../auth'
import { SkillsCheck } from '../components/supervision/SkillsCheck'
import { PublicationGap } from '../components/supervision/PublicationGap'

const LEVELS = ['BSc', 'MSc', 'PhD', 'Postdoc', 'IR', 'Other']

export function JourneyPage() {
  const { role, isAdmin, token } = useAuth()
  const qc = useQueryClient()
  const isStudent = role === 'student' && !isAdmin
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: api.me, enabled: isStudent })
  const [studentId, setStudentId] = useState('')
  const [form, setForm] = useState({
    level: 'MSc', status: 'active', programme: '', university: '', department: '',
    start_year: '', start_date: '', expected_end: '', thesis_title: '',
  })
  const [msg, setMsg] = useState<string | null>(null)

  const { data: users } = useQuery({ queryKey: ['users'], queryFn: () => api.listUsers() })
  const students = (users || []).filter(u => u.role === 'student' || (!u.is_admin && u.role !== 'professor'))

  const targetId = isStudent ? '' : studentId
  // Students rate themselves; a supervisor rates the student picked above.
  const skillsStudentId = isStudent ? me?.id : studentId || undefined
  const { data: journeys } = useQuery({
    queryKey: ['journeys', targetId],
    queryFn: () => supervisionApi.listJourneys(targetId || undefined),
  })

  const { data: requirements } = useQuery({
    queryKey: ['requirements'],
    queryFn: () => supervisionApi.listRequirements(),
  })

  const readinessStudentId = isStudent ? undefined : (studentId || undefined)
  const { data: readiness } = useQuery({
    queryKey: ['readiness', readinessStudentId],
    queryFn: () => supervisionApi.readiness(readinessStudentId),
  })

  const firstJourneyId = journeys?.[0]?.id || null
  const [activeJourneyId, setActiveJourneyId] = useState<string | null>(null)

  async function createJourney() {
    try {
      await supervisionApi.createJourney({
        level: form.level,
        status: form.status,
        programme: form.programme || undefined,
        university: form.university || undefined,
        department: form.department || undefined,
        start_year: form.start_year ? Number(form.start_year) : undefined,
        start_date: form.start_date || undefined,
        expected_end: form.expected_end || undefined,
        thesis_title: form.thesis_title || undefined,
      }, targetId || undefined)
      setMsg('Journey created.')
      await qc.invalidateQueries({ queryKey: ['journeys'] })
    } catch (e: any) {
      setMsg(e.message)
    }
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1000 }}>
      <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', color: 'var(--text-dim)' }}>Longitudinal view</div>
      <h1 style={{ margin: '4px 0 6px', fontSize: 22, color: 'var(--text-heading)' }}>
        {isStudent ? 'My journey' : 'Student journeys'}
      </h1>
      <p style={{ color: 'var(--text-2)', margin: '0 0 18px', fontSize: 14 }}>
        Track degree progress, thesis title, and graduation readiness.
      </p>

      {msg && <div style={{ padding: '8px 12px', marginBottom: 14, borderRadius: 6, background: 'rgba(var(--accent-rgb),0.12)', border: '1px solid rgba(var(--accent-rgb),0.3)' }}>{msg}</div>}

      {!isStudent && (
        <div style={{ marginBottom: 18 }}>
          <select value={studentId} onChange={e => setStudentId(e.target.value)} style={inputStyle}>
            <option value="">All students…</option>
            {students.map(u => <option key={u.id} value={u.id}>{u.username}</option>)}
          </select>
        </div>
      )}

      {skillsStudentId && (
        <div style={{ marginBottom: 24 }}>
          <SkillsCheck studentId={skillsStudentId} perspective={isStudent ? 'self' : 'supervisor'} />
        </div>
      )}
      <section style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 15, color: 'var(--text-heading)', margin: '0 0 10px' }}>Graduation readiness</h2>
        {readiness ? (
          <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 16, background: 'var(--surface-panel)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div style={{ fontSize: 14, color: 'var(--text-2)' }}>
                {readiness.level ? `${readiness.level} programme` : 'No active journey'}
                {readiness.thesis_title ? ` · ${readiness.thesis_title}` : ''}
              </div>
              <div style={{ fontSize: 17, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>
                {readiness.readiness_pct}%
              </div>
            </div>
            <div style={{ height: 10, background: 'var(--surface-input)', borderRadius: 5, overflow: 'hidden', marginBottom: 14 }}>
              <div style={{ height: '100%', width: `${readiness.readiness_pct}%`, background: 'var(--accent)', borderRadius: 5 }} />
            </div>
            <div style={{ display: 'grid', gap: 8 }}>
              {readiness.requirements.map(req => (
                <div key={req.id} style={{
                  display: 'flex', gap: 10, alignItems: 'center', fontSize: 13,
                  padding: '8px 10px', borderRadius: 6,
                  background: req.met ? 'rgba(var(--accent-rgb),0.08)' : 'var(--surface-input)',
                  border: req.met ? '1px solid rgba(var(--accent-rgb),0.25)' : '1px solid var(--border)',
                }}>
                  <span style={{ width: 18, color: req.met ? 'var(--accent)' : 'var(--text-dim)' }}>{req.met ? '✓' : '○'}</span>
                  <span style={{ flex: 1 }}>{req.title}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-2)', fontSize: 12 }}>
                    {req.current_value}/{req.target_value} {req.unit || req.req_type}
                  </span>
                </div>
              ))}
              {!readiness.requirements.length && (
                <div style={{ color: 'var(--text-2)', fontSize: 13 }}>No requirements defined for this level.</div>
              )}
            </div>
            <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-2)', display: 'flex', gap: 14, flexWrap: 'wrap' }}>
              <span>Publications: {readiness.summary.publications}</span>
              <span>Journal: {readiness.summary.journal_papers}</span>
              <span>Conference: {readiness.summary.conference_papers}</span>
            </div>
            <PublicationGap gap={readiness.publication_gap} />
          </div>
        ) : (
          <p style={{ color: 'var(--text-2)', fontSize: 14 }}>Create a journey to see readiness against graduation requirements.</p>
        )}
      </section>

      <section style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 15, color: 'var(--text-heading)', margin: '0 0 10px' }}>Journeys</h2>
        {(journeys || []).map(j => (
          <div key={j.id} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 14, marginBottom: 10, background: 'var(--surface-panel)' }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
              <strong style={{ fontSize: 15 }}>{j.level}</strong>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', padding: '2px 8px', borderRadius: 999, border: '1px solid var(--border)', color: 'var(--text-2)' }}>{j.status}</span>
            </div>
            {j.thesis_title && <div style={{ fontSize: 14, marginBottom: 4 }}>{j.thesis_title}</div>}
            <div style={{ fontSize: 12, color: 'var(--text-2)' }}>
              {[j.programme, j.department, j.university].filter(Boolean).join(' · ')}
              {j.start_date ? ` · ${j.start_date}` : ''}{j.expected_end ? ` → ${j.expected_end}` : ''}
            </div>
          </div>
        ))}
        {!journeys?.length && <p style={{ color: 'var(--text-2)', fontSize: 14 }}>No academic journey yet.</p>}
      </section>

      <section>
        <details className="disclosure">
          <summary>+ Add journey</summary>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, maxWidth: 720, marginTop: 12 }}>
            <label className="field"><span>Level</span>
              <select value={form.level} onChange={e => setForm(f => ({ ...f, level: e.target.value }))} style={inputStyle}>
                {LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </label>
            <label className="field"><span>Status</span>
              <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))} style={inputStyle}>
                <option value="planned">Planned</option>
                <option value="active">Active</option>
              </select>
            </label>
            <label className="field"><span>Programme</span>
              <input value={form.programme} onChange={e => setForm(f => ({ ...f, programme: e.target.value }))} style={inputStyle} /></label>
            <label className="field"><span>University</span>
              <input value={form.university} onChange={e => setForm(f => ({ ...f, university: e.target.value }))} style={inputStyle} /></label>
            <label className="field"><span>Department</span>
              <input value={form.department} onChange={e => setForm(f => ({ ...f, department: e.target.value }))} style={inputStyle} /></label>
            <label className="field"><span>Start year</span>
              <input type="number" value={form.start_year} onChange={e => setForm(f => ({ ...f, start_year: e.target.value }))} style={inputStyle} /></label>
            <label className="field"><span>Start date</span>
              <input type="date" value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} style={inputStyle} /></label>
            <label className="field"><span>Expected end</span>
              <input type="date" value={form.expected_end} onChange={e => setForm(f => ({ ...f, expected_end: e.target.value }))} style={inputStyle} /></label>
            <label className="field" style={{ gridColumn: '1 / -1' }}><span>Thesis / research title</span>
              <input value={form.thesis_title} onChange={e => setForm(f => ({ ...f, thesis_title: e.target.value }))} style={inputStyle} /></label>
          </div>
          <button onClick={createJourney} style={{ ...btnPrimary, marginTop: 12 }}>Create journey</button>
        </details>
      </section>

      <section style={{ marginTop: 28 }}>
        <h2 style={{ fontSize: 15, color: 'var(--text-heading)', margin: '0 0 10px' }}>Graduation requirements (reference)</h2>
        <div style={{ display: 'grid', gap: 8 }}>
          {(requirements || []).filter(r => r.active).map(r => (
            <div key={r.id} style={{ fontSize: 13, padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, display: 'flex', gap: 10 }}>
              <strong style={{ minWidth: 48 }}>{r.level}</strong>
              <span style={{ flex: 1 }}>{r.title}</span>
              <span style={{ color: 'var(--text-2)' }}>{r.target_value} {r.unit || r.req_type}</span>
            </div>
          ))}
          {!requirements?.length && <p style={{ color: 'var(--text-2)' }}>No requirements defined.</p>}
        </div>
      </section>
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
  background: 'var(--accent)', border: 'none', borderRadius: 6, color: '#fff',
}
