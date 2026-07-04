import React, { useEffect, useState } from 'react'
import { useAuth } from '../auth'

interface Lab {
  id: string; name: string; department: string
  member_count: number; members: { user_id: string; role: string }[]
}

interface PiStats {
  labs: Lab[]
  total_tasks: number; total_experiments: number
  recent_projects: { id: string; name: string; created_at: string }[]
  task_statuses: Record<string, number>
  experiment_statuses: Record<string, number>
  publication_statuses: Record<string, number>
  publications_over_time: { month: string; count: number }[]
}

const COLORS = ['#ff8015', '#6366f1', '#10b981', '#f59e0b', '#ec4899', '#f43f5e', '#8b5cf6']

function BarChart({ data, label, color }: { data: { label: string; value: number }[]; label: string; color: string }) {
  const max = Math.max(...data.map(d => d.value), 1)
  const h = 160
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'end', gap: 4, height: h, padding: '0 4px' }}>
        {data.map((d, i) => (
          <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-2)', fontFamily: 'var(--font-mono)' }}>{d.value}</span>
            <div style={{
              width: '100%', height: `${(d.value / max) * (h - 30)}px`,
              background: color, borderRadius: '4px 4px 0 0', opacity: 0.8,
              transition: 'height 0.3s ease',
            }} />
            <span style={{ fontSize: 13, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', writingMode: 'vertical-lr', textOrientation: 'mixed', height: 40, transform: 'rotate(180deg)' }}>
              {d.label}
            </span>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', textAlign: 'center', marginTop: 8 }}>{label}</div>
    </div>
  )
}

function DonutChart({ data }: { data: { label: string; value: number; color: string }[] }) {
  const total = data.reduce((s, d) => s + d.value, 0)
  if (total === 0) return <div style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', padding: 20, textAlign: 'center' }}>No data</div>
  const r = 60; const circ = 2 * Math.PI * r
  let offset = 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 24, justifyContent: 'center' }}>
      <svg width={160} height={160} viewBox="0 0 160 160">
        <circle cx={80} cy={80} r={r} fill="none" stroke="var(--border)" strokeWidth={20} />
        {data.map((d, i) => {
          const seg = (d.value / total) * circ
          const segOffset = offset
          offset += seg
          return (
            <circle key={i} cx={80} cy={80} r={r} fill="none" stroke={d.color} strokeWidth={20}
              strokeDasharray={`${seg} ${circ - seg}`} strokeDashoffset={-segOffset}
              transform="rotate(-90 80 80)" style={{ transition: 'stroke-dasharray 0.4s ease' }} />
          )
        })}
        <text x={80} y={80} textAnchor="middle" dominantBaseline="central"
          style={{ fontSize: 28, fontWeight: 700, fill: 'var(--text-heading)', fontFamily: 'var(--font-mono)' }}>
          {total}
        </text>
      </svg>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {data.map((d, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: d.color }} />
            <span style={{ fontSize: 15, fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>{d.label}</span>
            <span style={{ fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>{d.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function AnalyticsPage() {
  const { token } = useAuth()
  const [stats, setStats] = useState<PiStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/v1/pi/stats', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(setStats)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [token])

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-dim)', fontSize: 19, fontFamily: 'var(--font-mono)' }}>LOADING…</div>
  if (error) return <div style={{ padding: 40, color: '#f43f5e' }}>{error}</div>
  if (!stats) return null

  const taskData = [
    { label: 'To Do', value: stats.task_statuses['todo'] || 0, color: '#f59e0b' },
    { label: 'Active', value: stats.task_statuses['in_progress'] || 0, color: '#ff8015' },
    { label: 'Done', value: stats.task_statuses['done'] || 0, color: '#10b981' },
  ]
  const expData = [
    { label: 'Planned', value: stats.experiment_statuses['planned'] || 0, color: '#f59e0b' },
    { label: 'Running', value: stats.experiment_statuses['running'] || 0, color: '#ff8015' },
    { label: 'Done', value: stats.experiment_statuses['completed'] || 0, color: '#10b981' },
  ]
  const pubData = [
    { label: 'Draft', value: stats.publication_statuses['draft'] || 0, color: '#6b7280' },
    { label: 'Submitted', value: stats.publication_statuses['submitted'] || 0, color: '#6366f1' },
    { label: 'Review', value: stats.publication_statuses['reviewing'] || 0, color: '#f59e0b' },
    { label: 'Accepted', value: stats.publication_statuses['accepted'] || 0, color: '#10b981' },
    { label: 'Published', value: stats.publication_statuses['published'] || 0, color: '#059669' },
  ]

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <div style={{ maxWidth: 900, margin: '0 auto', padding: '32px 28px' }}>
        <h1 style={{ margin: '0 0 24px', fontSize: 30, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>
          Lab Analytics
        </h1>

        {/* Summary cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 28 }}>
          <SummaryCard value={stats.total_tasks} label="TASKS" color="#ff8015" />
          <SummaryCard value={stats.total_experiments} label="EXPERIMENTS" color="#6366f1" />
          <SummaryCard value={stats.recent_projects.length} label="PROJECTS" color="#10b981" />
          <SummaryCard value={stats.labs.length} label="LABS" color="#8b5cf6" />
        </div>

        {/* Charts row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 28 }}>
          <div style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: 20 }}>
            <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)', marginBottom: 16 }}>Tasks</div>
            <DonutChart data={taskData} />
          </div>
          <div style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: 20 }}>
            <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)', marginBottom: 16 }}>Experiments</div>
            <DonutChart data={expData} />
          </div>
        </div>

        {/* Publications */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 28 }}>
          <div style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: 20 }}>
            <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)', marginBottom: 16 }}>Publications</div>
            <DonutChart data={pubData} />
          </div>
          {stats.publications_over_time.length > 0 && (
            <div style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: 20 }}>
              <BarChart
                data={stats.publications_over_time.map(p => ({ label: p.month, value: p.count }))}
                label="Accepted/Published per Month"
                color="#10b981"
              />
            </div>
          )}
        </div>

        {/* Labs */}
        <h2 style={{ margin: '0 0 16px', fontSize: 22, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>Labs</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {stats.labs.map((lab, i) => (
            <div key={lab.id} style={{
              background: 'var(--surface-card)', border: '1px solid var(--border)',
              borderRadius: 10, padding: '14px 18px',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <div>
                <div style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-heading)' }}>{lab.name}</div>
                <div style={{ fontSize: 17, color: 'var(--text-dim)', marginTop: 2 }}>{lab.department}</div>
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 17, color: 'var(--text-dim)' }}>
                {lab.member_count} member{lab.member_count !== 1 ? 's' : ''}
              </div>
            </div>
          ))}
        </div>

        {/* Recent projects */}
        <h2 style={{ margin: '28px 0 16px', fontSize: 22, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>Recent Projects</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {stats.recent_projects.map(p => (
            <div key={p.id} style={{
              background: 'var(--surface-card)', border: '1px solid var(--border)',
              borderRadius: 10, padding: '12px 18px',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <span style={{ fontSize: 19, fontWeight: 500, color: 'var(--text-heading)' }}>{p.name}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 15, color: 'var(--text-dim)' }}>{new Date(p.created_at).toLocaleDateString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function SummaryCard({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '18px 20px', textAlign: 'center' }}>
      <div style={{ fontSize: 36, fontWeight: 700, color, fontFamily: 'var(--font-mono)' }}>{value}</div>
      <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 4, letterSpacing: '0.08em' }}>{label}</div>
    </div>
  )
}
