import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { AiUsagePanel } from '../components/AiUsagePanel'

/** Role-aware landing: each role gets its primary actions, not a generic dump. */
export function HomePage() {
  const { username, role, isAdmin } = useAuth()
  const navigate = useNavigate()

  const isStudent = role === 'student' && !isAdmin
  const isProfessor = role === 'professor' && !isAdmin

  const cards: { title: string; desc: string; path: string }[] = isAdmin
    ? [
        { title: 'Admin dashboard', desc: 'System stats, labs, users', path: '/admin' },
        { title: 'People', desc: 'Create users and assign roles', path: '/users' },
        { title: 'Graduation requirements', desc: 'Level-based rules for programmes', path: '/requirements' },
        { title: 'Reports', desc: 'Weekly supervision submissions', path: '/supervision/reports' },
      ]
    : isProfessor
      ? [
          { title: 'Professor dashboard', desc: 'KPIs, trends, workload, attention list', path: '/professor' },
          { title: 'Weekly meeting', desc: 'Attendance, follow-ups, extensions', path: '/meeting' },
          { title: 'Review reports', desc: 'Student weekly submissions', path: '/supervision/reports' },
          { title: 'Student journeys', desc: 'BSc / MSc / PhD progress', path: '/journey' },
        ]
      : [
          { title: 'Weekly update', desc: 'Submit this week’s progress', path: '/weekly-update' },
          { title: 'My journey', desc: 'Degree progress and publication readiness', path: '/journey' },
          { title: 'My tasks', desc: 'What is due soon', path: '/projects' },
          { title: 'Papers & research', desc: 'Publications and labs', path: '/publications' },
        ]

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1100 }}>
      <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', color: 'var(--text-dim)', marginBottom: 6 }}>
        {isAdmin ? 'Admin' : isProfessor ? 'Professor' : 'Student'} workspace
      </div>
      <h1 style={{ margin: '0 0 6px', fontSize: 24, color: 'var(--text-heading)' }}>
        Welcome, {username}
      </h1>
      <p style={{ color: 'var(--text-2)', margin: '0 0 28px', fontSize: 15 }}>
        {isStudent && 'Submit your weekly update, track your journey, and see what is due next.'}
        {isProfessor && 'Review student progress, run the weekly meeting, and clear follow-ups.'}
        {isAdmin && 'Manage people, requirements, and system health.'}
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 14 }}>
        {cards.map(c => (
          <button
            key={c.path}
            onClick={() => navigate(c.path)}
            style={{
              textAlign: 'left', padding: '18px 16px', cursor: 'pointer',
              background: 'var(--surface-panel)', border: '1px solid var(--border)',
              borderRadius: 8, color: 'var(--text)',
            }}
          >
            <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 6, color: 'var(--text-heading)' }}>{c.title}</div>
            <div style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.45 }}>{c.desc}</div>
          </button>
        ))}
      </div>

      <div style={{ marginTop: 26, maxWidth: 620 }}>
        <AiUsagePanel title="My AI usage" days={30} />
      </div>
    </div>
  )
}
