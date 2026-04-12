// src/pages/GlobalReportPage.tsx
import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import type { Project, Task, Experiment } from '../api'
import { StatCard } from '../components/report/StatCard'
import { SectionHeader } from '../components/report/SectionHeader'
import { BarChart } from '../components/report/BarChart'

function completionColor(pct: number): string {
  if (pct >= 80) return '#10b981'
  if (pct >= 40) return '#f59e0b'
  return '#f43f5e'
}

export function GlobalReportPage() {
  const navigate = useNavigate()

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: api.listProjects,
  })

  const { data: allProjectData = [] } = useQuery({
    queryKey: ['globalReport', projects.map(p => p.id).join(',')],
    queryFn: async () => {
      const results = await Promise.all(
        projects.map(async (project) => {
          const [tasks, experiments] = await Promise.all([
            api.listTasks(project.id),
            api.listExperiments(project.id),
          ])
          return { project, tasks, experiments }
        })
      )
      return results as { project: Project; tasks: Task[]; experiments: Experiment[] }[]
    },
    enabled: projects.length > 0,
  })

  const totalTasks  = allProjectData.reduce((sum, { tasks }) => sum + tasks.length, 0)
  const totalDone   = allProjectData.reduce((sum, { tasks }) => sum + tasks.filter(t => t.status === 'done').length, 0)
  const totalExps   = allProjectData.reduce((sum, { experiments }) => sum + experiments.length, 0)
  const runningExps = allProjectData.reduce((sum, { experiments }) => sum + experiments.filter(e => e.status === 'running').length, 0)

  const taskCompletionRows = allProjectData.map(({ project, tasks }) => {
    const done  = tasks.filter(t => t.status === 'done').length
    const total = tasks.length
    const pct   = total > 0 ? Math.round((done / total) * 100) : 0
    return { label: project.name, value: done, max: total || 1, color: completionColor(pct), sublabel: `${pct}%` }
  })

  const expStatusRows = allProjectData.map(({ project, experiments }) => {
    const planned   = experiments.filter(e => e.status === 'planned').length
    const running   = experiments.filter(e => e.status === 'running').length
    const completed = experiments.filter(e => e.status === 'completed').length
    return {
      label: project.name,
      value: experiments.length,
      max: experiments.length || 1,
      color: '#f59e0b',
      sublabel: String(experiments.length),
      segments: [
        { value: planned,   color: '#f59e0b' },
        { value: running,   color: '#ff8015' },
        { value: completed, color: '#10b981' },
      ],
    }
  })

  const generatedAt = new Date().toLocaleString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>

      {/* Header */}
      <div style={{
        padding: '0 28px', height: 54,
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'var(--surface-header)', backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            onClick={() => navigate('/projects')}
            style={{
              cursor: 'pointer', background: 'var(--surface-input)',
              border: '1px solid var(--border)', borderRadius: 6,
              color: 'var(--text-muted)', padding: '3px 9px', fontSize: 22, lineHeight: 1,
            }}
          >←</button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <img src="/sabita.jpg" alt="SABITA" style={{ height: 26, borderRadius: 4, display: 'block' }} />
            <span style={{ color: 'var(--text-dim)', fontSize: 20, fontFamily: 'var(--font-mono)' }}>/</span>
            <span style={{ color: '#ff8015', fontSize: 21, fontFamily: 'var(--font-mono)' }}>reports</span>
          </div>
        </div>
        <span style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
          Generated {generatedAt}
        </span>
      </div>

      {/* Content */}
      <div style={{ maxWidth: 900, margin: '0 auto', padding: '32px 28px 64px' }}>

        {/* Section 1 — Global Summary */}
        <div style={{ marginBottom: 40 }}>
          <SectionHeader title="Global Summary" accent="#ff8015" count={projects.length > 0 ? projects.length : undefined} />
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <StatCard value={projects.length} label="Total Projects" accent="#ff8015" />
            <StatCard value={totalDone}   label="Tasks Completed"     accent="#10b981" sublabel={`of ${totalTasks} total`} />
            <StatCard value={totalExps}   label="Total Experiments"   accent="#f59e0b" />
            <StatCard value={runningExps} label="Running Experiments" accent="#f43f5e" />
          </div>
        </div>

        {/* Section 2 — Task Completion by Project */}
        <div style={{ marginBottom: 40 }}>
          <SectionHeader title="Task Completion by Project" accent="#ff8015" />
          <div style={{
            background: 'var(--surface-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 8, padding: '20px 24px',
          }}>
            {allProjectData.length === 0 ? (
              <span style={{ color: 'var(--text-dim)', fontSize: 16, fontFamily: 'var(--font-mono)' }}>
                No data yet
              </span>
            ) : (
              <BarChart rows={taskCompletionRows} rowHeight={28} />
            )}
          </div>
        </div>

        {/* Section 3 — Experiment Status by Project */}
        <div style={{ marginBottom: 40 }}>
          <SectionHeader title="Experiment Status by Project" accent="#10b981" />
          <div style={{
            background: 'var(--surface-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 8, padding: '20px 24px',
          }}>
            {allProjectData.length === 0 ? (
              <span style={{ color: 'var(--text-dim)', fontSize: 16, fontFamily: 'var(--font-mono)' }}>
                No data yet
              </span>
            ) : (
              <BarChart rows={expStatusRows} rowHeight={28} />
            )}
          </div>
        </div>

        {/* Section 4 — Project Summary Table */}
        <div style={{ marginBottom: 40 }}>
          <SectionHeader title="All Projects" accent="#ff8015" count={projects.length > 0 ? projects.length : undefined} />
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 16 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['PROJECT', 'TASKS', 'EXPERIMENTS', 'MEMBERS', ''].map(h => (
                  <th key={h} style={{
                    padding: '6px 8px', textAlign: 'left',
                    fontSize: 18, fontFamily: 'var(--font-mono)',
                    color: 'var(--text-dim)', letterSpacing: '0.1em',
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {allProjectData.map(({ project, tasks, experiments }) => {
                const done = tasks.filter(t => t.status === 'done').length
                return (
                  <tr key={project.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '10px 8px', color: 'var(--text-heading)', fontWeight: 500 }}>
                      {project.name}
                    </td>
                    <td style={{ padding: '10px 8px', fontFamily: 'var(--font-mono)', fontSize: 16, color: 'var(--text-dim)' }}>
                      {done}/{tasks.length}
                    </td>
                    <td style={{ padding: '10px 8px', fontFamily: 'var(--font-mono)', fontSize: 16, color: 'var(--text-dim)' }}>
                      {experiments.length}
                    </td>
                    <td style={{ padding: '10px 8px', fontFamily: 'var(--font-mono)', fontSize: 16, color: 'var(--text-dim)' }}>
                      {project.members.length}
                    </td>
                    <td style={{ padding: '10px 8px' }}>
                      <button
                        onClick={() => navigate(`/projects/${project.id}/report`)}
                        style={{
                          background: 'rgba(255,128,21,0.08)',
                          border: '1px solid rgba(255,128,21,0.2)',
                          color: '#ff8015', fontFamily: 'var(--font-mono)',
                          fontSize: 18, padding: '3px 8px',
                          borderRadius: 3, cursor: 'pointer', letterSpacing: '0.08em',
                        }}
                      >
                        → VIEW REPORT
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

      </div>
    </div>
  )
}
