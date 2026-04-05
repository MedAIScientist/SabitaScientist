import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Project, Task, Experiment } from '../api'
import { useAuth } from '../auth'
import { useTheme } from '../theme'

const ACCENT_CYCLE = ['#ff8015', '#f59e0b', '#10b981', '#8b5cf6', '#ec4899', '#f43f5e']

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

// ── Per-project stats card ────────────────────────────────────────────────────
function ProjectCard({ project, accent, index }: { project: Project; accent: string; index: number }) {
  const navigate = useNavigate()

  const { data: tasks = [] } = useQuery<Task[]>({
    queryKey: ['tasks', project.id],
    queryFn: () => api.listTasks(project.id),
  })

  const { data: experiments = [] } = useQuery<Experiment[]>({
    queryKey: ['experiments', project.id],
    queryFn: () => api.listExperiments(project.id),
  })

  const todo        = tasks.filter(t => t.status === 'todo').length
  const inProgress  = tasks.filter(t => t.status === 'in_progress').length
  const done        = tasks.filter(t => t.status === 'done').length
  const total       = tasks.length

  const expPlanned   = experiments.filter(e => e.status === 'planned').length
  const expRunning   = experiments.filter(e => e.status === 'running').length
  const expCompleted = experiments.filter(e => e.status === 'completed').length

  const showMembers = project.members.slice(0, 4)
  const extraMembers = project.members.length - showMembers.length

  return (
    <div
      style={{
        background: 'var(--surface-card)',
        border: '1px solid var(--border-subtle)',
        borderLeft: `3px solid ${accent}`,
        borderRadius: '0 10px 10px 0',
        cursor: 'pointer',
        transition: 'background 0.14s, transform 0.14s, box-shadow 0.14s',
        animation: 'fadeInUp 0.22s ease both',
        animationDelay: `${index * 0.05}s`,
        overflow: 'hidden',
      }}
      onMouseEnter={e => {
        const el = e.currentTarget
        el.style.background = 'var(--surface-card-hover)'
        el.style.transform = 'translateX(3px)'
        el.style.boxShadow = `0 4px 20px rgba(0,0,0,0.18), -2px 0 0 ${accent}`
      }}
      onMouseLeave={e => {
        const el = e.currentTarget
        el.style.background = 'var(--surface-card)'
        el.style.transform = ''
        el.style.boxShadow = ''
      }}
      onClick={() => navigate(`/projects/${project.id}`)}
    >
      {/* Main content */}
      <div style={{ padding: '14px 18px 10px' }}>
        {/* Title row */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 4 }}>
          <strong style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-heading)', lineHeight: 1.3, flex: 1, marginRight: 12 }}>
            {project.name}
          </strong>
          {/* Quick-action buttons */}
          <div style={{ display: 'flex', gap: 5, flexShrink: 0 }} onClick={e => e.stopPropagation()}>
            <button
              onClick={() => navigate(`/projects/${project.id}`)}
              title="Kanban Board"
              style={{
                background: 'rgba(255,128,21,0.08)', border: '1px solid rgba(255,128,21,0.22)',
                borderRadius: 4, padding: '3px 8px', fontSize: 10, color: '#ff8015',
                cursor: 'pointer', fontFamily: 'var(--font-mono)', fontWeight: 700, letterSpacing: '0.06em',
              }}
            >⊞ BOARD</button>
            <button
              onClick={() => navigate(`/projects/${project.id}/experiments`)}
              title="Experiments"
              style={{
                background: 'rgba(16,185,129,0.07)', border: '1px solid rgba(16,185,129,0.2)',
                borderRadius: 4, padding: '3px 8px', fontSize: 10, color: '#10b981',
                cursor: 'pointer', fontFamily: 'var(--font-mono)', fontWeight: 700, letterSpacing: '0.06em',
              }}
            >⚗ EXPS</button>
          </div>
        </div>

        {/* Description */}
        {project.description && (
          <p style={{ margin: '0 0 10px', color: 'var(--text-2)', fontSize: 13, lineHeight: 1.5 }}>
            {project.description}
          </p>
        )}

        {/* Task progress bar */}
        {total > 0 && (
          <div style={{ marginBottom: 10 }}>
            <div style={{ display: 'flex', height: 4, borderRadius: 2, overflow: 'hidden', gap: 1 }}>
              {todo > 0 && (
                <div style={{ flex: todo, background: 'rgba(255,128,21,0.45)', borderRadius: 2 }} title={`${todo} planned`} />
              )}
              {inProgress > 0 && (
                <div style={{ flex: inProgress, background: '#f59e0b', borderRadius: 2 }} title={`${inProgress} in progress`} />
              )}
              {done > 0 && (
                <div style={{ flex: done, background: '#10b981', borderRadius: 2 }} title={`${done} done`} />
              )}
            </div>
          </div>
        )}

        {/* Stats row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          {/* Task counts */}
          {total > 0 ? (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              {todo > 0 && (
                <span style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: 3 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'rgba(255,128,21,0.6)', display: 'inline-block' }} />
                  {todo} PLANNED
                </span>
              )}
              {inProgress > 0 && (
                <span style={{ fontSize: 10, color: '#f59e0b', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: 3 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#f59e0b', display: 'inline-block' }} />
                  {inProgress} ACTIVE
                </span>
              )}
              {done > 0 && (
                <span style={{ fontSize: 10, color: '#10b981', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: 3 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
                  {done} DONE
                </span>
              )}
            </div>
          ) : (
            <span style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>NO TASKS</span>
          )}

          {/* Experiment counts */}
          {experiments.length > 0 && (
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>·</span>
              {expPlanned > 0 && (
                <span style={{ fontSize: 10, color: '#f59e0b', fontFamily: 'var(--font-mono)' }}>⚗ {expPlanned} PLANNED</span>
              )}
              {expRunning > 0 && (
                <span style={{ fontSize: 10, color: '#ff8015', fontFamily: 'var(--font-mono)' }}>⚗ {expRunning} RUNNING</span>
              )}
              {expCompleted > 0 && (
                <span style={{ fontSize: 10, color: '#10b981', fontFamily: 'var(--font-mono)' }}>⚗ {expCompleted} DONE</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div style={{
        padding: '8px 18px',
        borderTop: '1px solid var(--border-subtle)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'var(--surface-2)',
      }}>
        {/* Member avatars */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {showMembers.map((m, mi) => (
            <div
              key={m.user_id}
              title={`${m.username} (${m.role})`}
              style={{
                width: 20, height: 20, borderRadius: '50%',
                background: ACCENT_CYCLE[(mi + 1) % ACCENT_CYCLE.length],
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 8, fontWeight: 700, color: '#fff',
                fontFamily: 'var(--font-mono)',
                border: '1px solid var(--surface-card)',
                marginLeft: mi > 0 ? -4 : 0,
                zIndex: showMembers.length - mi,
                position: 'relative',
              }}
            >
              {m.username[0].toUpperCase()}
            </div>
          ))}
          {extraMembers > 0 && (
            <span style={{ fontSize: 8, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginLeft: 4 }}>
              +{extraMembers}
            </span>
          )}
        </div>

        {/* Created date */}
        <span style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
          {formatDate(project.created_at)}
        </span>
      </div>
    </div>
  )
}

// ── Main Projects page ────────────────────────────────────────────────────────
export function Projects() {
  const { username } = useAuth()
  const { theme } = useTheme()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [creating, setCreating] = useState(false)

  const { data: projects = [], isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: api.listProjects,
    refetchInterval: 30_000,
  })

  const createMutation = useMutation({
    mutationFn: ({ name, description }: { name: string; description?: string }) =>
      api.createProject(name, description),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setNewName('')
      setNewDesc('')
      setCreating(false)
    },
  })

  if (isLoading) return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100vh', color: 'var(--text-muted)',
      fontFamily: 'var(--font-mono)', fontSize: 13, letterSpacing: '0.08em',
    }}>
      LOADING…
    </div>
  )

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>

      {/* ── Header ── */}
      <div style={{
        padding: '0 28px', height: 54,
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'var(--surface-header)', backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <img src="/sabita.jpg" alt="SABITA" style={{ height: 26, borderRadius: 4, display: 'block' }} />
          <span style={{ color: 'var(--text-dim)', fontSize: 13, fontFamily: 'var(--font-mono)' }}>/</span>
          <span style={{ color: '#ff8015', fontSize: 14, fontFamily: 'var(--font-mono)' }}>projects</span>
        </div>
        <button
          onClick={() => navigate('/profile')}
          title={username ?? 'Profile'}
          style={{
            width: 30, height: 30, borderRadius: '50%', border: 'none',
            background: theme === 'dark'
              ? 'linear-gradient(135deg, rgba(255,128,21,0.25), rgba(139,92,246,0.25))'
              : 'linear-gradient(135deg, rgba(255,128,21,0.4), rgba(139,92,246,0.4))',
            color: '#ff8015',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 13, fontWeight: 700, cursor: 'pointer',
            fontFamily: 'var(--font-mono)',
            outline: '1px solid rgba(255,128,21,0.25)',
            transition: 'outline-color 0.15s, box-shadow 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.outlineColor = 'rgba(255,128,21,0.6)'; e.currentTarget.style.boxShadow = '0 0 10px rgba(255,128,21,0.2)' }}
          onMouseLeave={e => { e.currentTarget.style.outlineColor = 'rgba(255,128,21,0.25)'; e.currentTarget.style.boxShadow = '' }}
        >
          {username?.[0]?.toUpperCase() ?? '?'}
        </button>
      </div>

      {/* ── Content ── */}
      <div style={{ maxWidth: 760, margin: '0 auto', padding: '40px 28px' }}>
        <div style={{ marginBottom: 28 }}>
          <h1 style={{ margin: '0 0 5px', fontSize: 25, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>
            Research Projects
          </h1>
          <p style={{ margin: 0, fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
            {projects.length} PROJECT{projects.length !== 1 ? 'S' : ''} · SYNCS EVERY 30S
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 24 }}>
          {projects.map((p: Project, i: number) => (
            <ProjectCard
              key={p.id}
              project={p}
              accent={ACCENT_CYCLE[i % ACCENT_CYCLE.length]}
              index={i}
            />
          ))}
          {projects.length === 0 && (
            <p style={{ color: 'var(--text-muted)', fontSize: 14, padding: '10px 0', fontStyle: 'italic' }}>
              No projects yet. Create your first one below.
            </p>
          )}
        </div>

        {creating ? (
          <form
            onSubmit={e => { e.preventDefault(); createMutation.mutate({ name: newName, description: newDesc || undefined }) }}
            style={{
              display: 'flex', flexDirection: 'column', gap: 8, padding: 14,
              background: 'var(--surface-card)',
              border: '1px solid rgba(255,128,21,0.18)',
              borderRadius: 8, animation: 'fadeInUp 0.18s ease',
            }}
          >
            <input
              autoFocus value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder="Project name…" required
              style={{
                padding: '8px 11px',
                background: 'var(--surface-input)',
                border: '1px solid rgba(255,128,21,0.2)',
                borderRadius: 6, color: 'var(--text)', fontSize: 15, outline: 'none',
              }}
            />
            <textarea
              value={newDesc}
              onChange={e => setNewDesc(e.target.value)}
              placeholder="Brief description (optional)…"
              rows={2}
              style={{
                padding: '6px 11px',
                background: 'var(--surface-input)',
                border: '1px solid rgba(255,128,21,0.2)',
                borderRadius: 6, color: 'var(--text)', fontSize: 14, outline: 'none',
                resize: 'none', fontFamily: 'inherit',
              }}
            />
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="submit" disabled={createMutation.isPending} style={{
                padding: '8px 16px', cursor: 'pointer',
                background: '#ff8015', color: '#06091a',
                border: 'none', borderRadius: 6, fontSize: 11, fontWeight: 700,
                letterSpacing: '0.06em', fontFamily: 'var(--font-mono)',
              }}>CREATE</button>
              <button type="button" onClick={() => setCreating(false)} style={{
                padding: '8px 12px', cursor: 'pointer',
                background: 'var(--surface-input)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 6, color: 'var(--text-3)', fontSize: 14,
              }}>✕</button>
            </div>
          </form>
        ) : (
          <button
            onClick={() => setCreating(true)}
            style={{
              padding: '9px 18px', cursor: 'pointer',
              background: 'rgba(255,128,21,0.07)',
              border: '1px solid rgba(255,128,21,0.18)',
              borderRadius: 7, color: '#ff8015',
              fontSize: 11, fontWeight: 700, letterSpacing: '0.08em',
              transition: 'background 0.14s',
              fontFamily: 'var(--font-mono)',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.13)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.07)' }}
          >+ NEW PROJECT</button>
        )}
      </div>
    </div>
  )
}
