// src/pages/ProjectReportPage.tsx
import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { StatCard } from '../components/report/StatCard'
import { DonutChart } from '../components/report/DonutChart'
import { SectionHeader } from '../components/report/SectionHeader'

const PRINT_CSS = `
@media print {
  .no-print { display: none !important; }
  body { background: white !important; color: black !important; }
  .report-section { break-inside: avoid; }
  .report-section--experiments { break-before: page; }
  .report-section--team { break-before: page; }
  .accordion-body { display: block !important; }
  @page { size: A4; margin: 20mm; }
}
`

const EXP_STATUS_COLORS: Record<string, string> = {
  planned: '#f59e0b',
  running: '#ff8015',
  completed: '#10b981',
}

const PRIORITY_COLORS: Record<string, string> = {
  high: '#f43f5e',
  medium: '#f59e0b',
  low: '#10b981',
}

const AVATAR_COLORS = ['#6366f1', '#ec4899', '#f59e0b', '#ff8015', '#10b981', '#8b5cf6']

const ROLE_COLORS: Record<string, string> = {
  owner: '#ff8015',
  editor: '#f59e0b',
  viewer: '#64748b',
}

function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '8px 12px',
      background: 'rgba(244,63,94,0.08)',
      border: '1px solid rgba(244,63,94,0.2)',
      borderRadius: 6, marginBottom: 12,
    }}>
      <span style={{ fontSize: 16, color: '#f43f5e', fontFamily: 'var(--font-mono)', flex: 1 }}>
        {message}
      </span>
      <button
        onClick={onRetry}
        style={{
          background: 'none',
          border: '1px solid rgba(244,63,94,0.3)',
          borderRadius: 4, color: '#f43f5e',
          fontSize: 15, cursor: 'pointer',
          padding: '3px 8px', fontFamily: 'var(--font-mono)',
        }}
      >
        RETRY
      </button>
    </div>
  )
}

export function ProjectReportPage() {
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [expandedExp, setExpandedExp] = useState<string | null>(null)

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.getProject(projectId!),
    enabled: Boolean(projectId),
  })

  const {
    data: tasks = [],
    isError: tasksError,
    refetch: refetchTasks,
  } = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => api.listTasks(projectId!),
    enabled: Boolean(projectId),
  })

  const { data: experiments = [] } = useQuery({
    queryKey: ['experiments', projectId],
    queryFn: () => api.listExperiments(projectId!),
    enabled: Boolean(projectId),
  })

  // listEntries requires per-experiment calls (projectId + expId); use empty counts
  const entryCounts = new Map<string, { notes: number; results: number }>()

  const todoCount       = tasks.filter(t => t.status === 'todo').length
  const inProgressCount = tasks.filter(t => t.status === 'in_progress').length
  const doneCount       = tasks.filter(t => t.status === 'done').length
  const donePercent     = tasks.length > 0 ? Math.round((doneCount / tasks.length) * 100) : 0

  const plannedCount   = experiments.filter(e => e.status === 'planned').length
  const runningCount   = experiments.filter(e => e.status === 'running').length
  const completedCount = experiments.filter(e => e.status === 'completed').length

  const sortedExps = [...experiments].sort((a, b) => {
    const order: Record<string, number> = { completed: 0, running: 1, planned: 2 }
    return (order[a.status] ?? 3) - (order[b.status] ?? 3)
  })

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <style>{PRINT_CSS}</style>

      {/* Header */}
      <div className="no-print" style={{
        padding: '0 28px', height: 54,
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'var(--surface-header)', backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            onClick={() => navigate(`/projects/${projectId}`)}
            style={{
              cursor: 'pointer', background: 'var(--surface-input)',
              border: '1px solid var(--border)', borderRadius: 6,
              color: 'var(--text-muted)', padding: '3px 9px', fontSize: 22, lineHeight: 1,
            }}
          >←</button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <img src="/sabita.jpg" alt="SABITA" style={{ height: 26, borderRadius: 4, display: 'block' }} />
            <span style={{ color: 'var(--text-dim)', fontSize: 20, fontFamily: 'var(--font-mono)' }}>/</span>
            <span style={{ color: '#ff8015', fontSize: 21, fontFamily: 'var(--font-mono)' }}>
              {project?.name ?? '…'}
            </span>
            <span style={{ color: 'var(--text-dim)', fontSize: 20, fontFamily: 'var(--font-mono)' }}>/</span>
            <span style={{ color: 'var(--text-muted)', fontSize: 20, fontFamily: 'var(--font-mono)' }}>report</span>
          </div>
        </div>
        <button
          onClick={() => window.print()}
          style={{
            background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.18)',
            color: '#10b981', fontFamily: 'var(--font-mono)', fontSize: 16,
            padding: '5px 14px', borderRadius: 4, cursor: 'pointer', letterSpacing: '0.08em',
          }}
        >
          ⬇ PDF
        </button>
      </div>

      {/* Content */}
      <div style={{ maxWidth: 900, margin: '0 auto', padding: '32px 28px 64px' }}>

        {/* Section 1 — Summary */}
        <div className="report-section" style={{ marginBottom: 40 }}>
          <SectionHeader title="Summary" accent="#ff8015" />
          {tasksError && (
            <ErrorBanner
              message="Could not load task data — please retry."
              onRetry={() => refetchTasks()}
            />
          )}
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <StatCard value={tasks.length}                  label="Total Tasks"  accent="#ff8015" />
            <StatCard value={`${donePercent}%`}             label="Done"         accent="#10b981" sublabel={`${doneCount} of ${tasks.length}`} />
            <StatCard value={experiments.length}            label="Experiments"  accent="#f59e0b" />
            <StatCard value={project?.members.length ?? 0}  label="Team Members" accent="#8b5cf6" />
          </div>
        </div>

        {/* Section 2 — Task Breakdown */}
        <div className="report-section" style={{ marginBottom: 40 }}>
          <SectionHeader title="Task Breakdown" accent="#ff8015" count={tasks.length} />
          <div style={{ display: 'flex', gap: 32, alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <DonutChart
              segments={[
                { value: todoCount,       color: '#ff8015', label: 'PLANNED' },
                { value: inProgressCount, color: '#f59e0b', label: 'IN PROG' },
                { value: doneCount,       color: '#10b981', label: 'DONE' },
              ]}
              size={140}
              strokeWidth={22}
            />
            <div style={{ flex: 1, minWidth: 200 }}>
              {[
                { label: 'PLANNED',     count: todoCount,       color: '#ff8015' },
                { label: 'IN PROGRESS', count: inProgressCount, color: '#f59e0b' },
                { label: 'DONE',        count: doneCount,       color: '#10b981' },
              ].map(({ label, count, color }) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: color, flexShrink: 0 }} />
                  <span style={{ fontSize: 16, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', flex: 1 }}>{label}</span>
                  <span style={{ fontSize: 20, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-heading)' }}>{count}</span>
                  <span style={{ fontSize: 15, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', width: 36, textAlign: 'right' }}>
                    {tasks.length > 0 ? Math.round((count / tasks.length) * 100) : 0}%
                  </span>
                </div>
              ))}
              <div style={{ marginTop: 16, borderTop: '1px solid var(--border-subtle)', paddingTop: 12 }}>
                <div style={{ fontSize: 18, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.1em', marginBottom: 8 }}>
                  PRIORITY BREAKDOWN
                </div>
                {(['high', 'medium', 'low'] as const).map(pri => {
                  const count = tasks.filter(t => t.priority === pri).length
                  return (
                    <div key={pri} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: PRIORITY_COLORS[pri], flexShrink: 0 }} />
                      <span style={{ fontSize: 15, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', flex: 1, textTransform: 'capitalize' }}>{pri}</span>
                      <span style={{ fontSize: 16, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)', fontWeight: 700 }}>{count}</span>
                      <span style={{ fontSize: 15, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', width: 36, textAlign: 'right' }}>
                        {tasks.length > 0 ? Math.round((count / tasks.length) * 100) : 0}%
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Section 3 — Experiment Overview */}
        <div className="report-section report-section--experiments" style={{ marginBottom: 40 }}>
          <SectionHeader title="Experiment Overview" accent="#10b981" count={experiments.length} />
          <div style={{ display: 'flex', gap: 32, alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: 20 }}>
            <DonutChart
              segments={[
                { value: plannedCount,   color: '#f59e0b', label: 'PLANNED' },
                { value: runningCount,   color: '#ff8015', label: 'RUNNING' },
                { value: completedCount, color: '#10b981', label: 'DONE' },
              ]}
              size={140}
              strokeWidth={22}
            />
            <div style={{ flex: 1, minWidth: 200 }}>
              {[
                { label: 'PLANNED',   count: plannedCount,   color: '#f59e0b' },
                { label: 'RUNNING',   count: runningCount,   color: '#ff8015' },
                { label: 'COMPLETED', count: completedCount, color: '#10b981' },
              ].map(({ label, count, color }) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: color, flexShrink: 0 }} />
                  <span style={{ fontSize: 16, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', flex: 1 }}>{label}</span>
                  <span style={{ fontSize: 20, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-heading)' }}>{count}</span>
                </div>
              ))}
            </div>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 16 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['NAME', 'STATUS', 'TAGS', 'DEADLINE', 'NOTES', 'RESULTS'].map(h => (
                  <th key={h} style={{ padding: '6px 8px', textAlign: 'left', fontSize: 18, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.1em' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedExps.map(exp => {
                const counts = entryCounts.get(exp.id) ?? { notes: 0, results: 0 }
                const statusColor = EXP_STATUS_COLORS[exp.status] ?? '#64748b'
                return (
                  <tr key={exp.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '8px', color: 'var(--text-heading)', fontWeight: 500 }}>{exp.name}</td>
                    <td style={{ padding: '8px' }}>
                      <span style={{
                        fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)',
                        color: statusColor, background: `${statusColor}18`,
                        border: `1px solid ${statusColor}33`,
                        borderRadius: 3, padding: '2px 6px',
                      }}>
                        {exp.status.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: '8px', fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                      {exp.tags.join(', ') || '—'}
                    </td>
                    <td style={{ padding: '8px', fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                      {exp.deadline ?? '—'}
                    </td>
                    <td style={{ padding: '8px', fontSize: 16, textAlign: 'center' }}>{counts.notes}</td>
                    <td style={{ padding: '8px', fontSize: 16, textAlign: 'center' }}>{counts.results}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Section 4 — Experiment Details (accordion) */}
        <div className="report-section" style={{ marginBottom: 40 }}>
          <SectionHeader title="Experiment Details" accent="#10b981" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {sortedExps.map(exp => {
              const isOpen = expandedExp === exp.id
              const counts = entryCounts.get(exp.id) ?? { notes: 0, results: 0 }
              const statusColor = EXP_STATUS_COLORS[exp.status] ?? '#64748b'
              return (
                <div key={exp.id} style={{ border: '1px solid var(--border-subtle)', borderRadius: 6, overflow: 'hidden' }}>
                  <button
                    onClick={() => setExpandedExp(isOpen ? null : exp.id)}
                    style={{
                      width: '100%', background: 'var(--surface-2)', border: 'none',
                      padding: '10px 14px', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: 10,
                      textAlign: 'left',
                    }}
                  >
                    <span style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                      {isOpen ? '▾' : '▸'}
                    </span>
                    <span style={{ flex: 1, fontSize: 20, fontWeight: 500, color: 'var(--text-heading)' }}>
                      {exp.name}
                    </span>
                    <span style={{
                      fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)',
                      color: statusColor, background: `${statusColor}18`,
                      border: `1px solid ${statusColor}33`,
                      borderRadius: 3, padding: '2px 6px',
                    }}>
                      {exp.status.toUpperCase()}
                    </span>
                  </button>
                  {isOpen && (
                    <div className="accordion-body" style={{
                      padding: '14px 16px',
                      borderTop: '1px solid var(--border-subtle)',
                      background: 'var(--surface-card)',
                    }}>
                      {exp.hypothesis && (
                        <div style={{ marginBottom: 10 }}>
                          <div style={{ fontSize: 18, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.1em', marginBottom: 4 }}>
                            HYPOTHESIS
                          </div>
                          <p style={{ fontSize: 18, color: 'var(--text)', lineHeight: 1.5, margin: 0 }}>
                            {exp.hypothesis.slice(0, 200)}{exp.hypothesis.length > 200 ? '…' : ''}
                          </p>
                        </div>
                      )}
                      {exp.protocol && (
                        <div style={{ marginBottom: 10 }}>
                          <div style={{ fontSize: 18, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.1em', marginBottom: 4 }}>
                            PROTOCOL
                          </div>
                          <p style={{ fontSize: 18, color: 'var(--text)', lineHeight: 1.5, margin: 0 }}>
                            {exp.protocol.slice(0, 200)}{exp.protocol.length > 200 ? '…' : ''}
                          </p>
                        </div>
                      )}
                      <div style={{ display: 'flex', gap: 16, marginTop: 10 }}>
                        <span style={{ fontSize: 16, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
                          <span style={{ color: '#f59e0b', fontWeight: 700 }}>{counts.notes}</span> notes
                        </span>
                        <span style={{ fontSize: 16, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
                          <span style={{ color: '#10b981', fontWeight: 700 }}>{counts.results}</span> results
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Section 5 — Team Activity */}
        <div className="report-section report-section--team" style={{ marginBottom: 40 }}>
          <SectionHeader title="Team Activity" accent="#8b5cf6" count={project?.members.length} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {(project?.members ?? []).map((member, i) => {
              const assigned  = tasks.filter(t => t.assignee_id === member.user_id).length
              const completed = tasks.filter(t => t.assignee_id === member.user_id && t.status === 'done').length
              const roleColor = ROLE_COLORS[member.role] ?? '#64748b'
              return (
                <div key={member.user_id} style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  background: 'var(--surface-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 7, padding: '10px 14px',
                }}>
                  <span style={{
                    width: 34, height: 34, borderRadius: '50%',
                    background: AVATAR_COLORS[i % AVATAR_COLORS.length],
                    color: '#fff',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-mono)', flexShrink: 0,
                  }}>
                    {member.username[0].toUpperCase()}
                  </span>
                  <span style={{ flex: 1, fontSize: 20, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)' }}>
                    {member.username}
                  </span>
                  <span style={{
                    fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)',
                    color: roleColor, background: `${roleColor}18`,
                    border: `1px solid ${roleColor}33`,
                    borderRadius: 3, padding: '2px 6px',
                  }}>
                    {member.role.toUpperCase()}
                  </span>
                  <div style={{ display: 'flex', gap: 16, fontSize: 16, fontFamily: 'var(--font-mono)' }}>
                    <span style={{ color: 'var(--text-dim)' }}>
                      Assigned: <strong style={{ color: 'var(--text-heading)' }}>{assigned}</strong>
                    </span>
                    <span style={{ color: 'var(--text-dim)' }}>
                      Done: <strong style={{ color: '#10b981' }}>{completed}</strong>
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

      </div>
    </div>
  )
}
