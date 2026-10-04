import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { supervisionApi } from '../../api'

const KEY = 'requirements-prompt-dismissed'

/** Asks a professor to set graduation requirements for student levels that have none. */
export function RequirementsPrompt() {
  const navigate = useNavigate()
  const [hidden, setHidden] = useState(() => { try { return sessionStorage.getItem(KEY) === '1' } catch { return false } })
  const { data: students = [] } = useQuery({ queryKey: ['students-overview'], queryFn: supervisionApi.studentsOverview })
  const { data: reqs } = useQuery({ queryKey: ['requirements'], queryFn: () => supervisionApi.listRequirements() })
  if (hidden || !reqs) return null

  const covered = new Set(reqs.map(r => r.level.toLowerCase()))
  const missing = new Map<string, number>()
  for (const s of students) {
    if (s.level && !covered.has(s.level.toLowerCase())) missing.set(s.level, (missing.get(s.level) ?? 0) + 1)
  }
  if (missing.size === 0) return null
  const who = [...missing].map(([level, n]) => `${level} (${n} student${n > 1 ? 's' : ''})`).join(', ')

  return (
    <section className="card" role="status" style={{ padding: '12px 16px', marginBottom: 16, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', borderLeft: '4px solid #f59e0b' }}>
      <div style={{ flex: 1, minWidth: 260 }}>
        <div style={{ fontWeight: 700 }}>Set graduation requirements for your students</div>
        <div style={{ fontSize: 14, color: 'var(--text-2)' }}>
          No requirements yet for: {who}. Until you add them, you and your students cannot see how close they are to graduating. Ready-made templates take a minute.
        </div>
      </div>
      <button className="btn btn-primary" onClick={() => navigate('/requirements')}>Set requirements</button>
      <button className="btn" onClick={() => { setHidden(true); try { sessionStorage.setItem(KEY, '1') } catch { /* private mode */ } }}>Later</button>
    </section>
  )
}
