import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Project, Task, Experiment, Template } from '../api'
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
          <strong style={{ fontSize: 21, fontWeight: 600, color: 'var(--text-heading)', lineHeight: 1.3, flex: 1, marginRight: 12 }}>
            {project.name}
          </strong>
          {/* Quick-action buttons */}
          <div style={{ display: 'flex', gap: 5, flexShrink: 0 }} onClick={e => e.stopPropagation()}>
            <button
              onClick={() => navigate(`/projects/${project.id}`)}
              title="Kanban Board"
              style={{
                background: 'rgba(255,128,21,0.08)', border: '1px solid rgba(255,128,21,0.22)',
                borderRadius: 4, padding: '3px 8px', fontSize: 15, color: '#ff8015',
                cursor: 'pointer', fontFamily: 'var(--font-mono)', fontWeight: 700, letterSpacing: '0.06em',
              }}
            >⊞ BOARD</button>
            <button
              onClick={() => navigate(`/projects/${project.id}/experiments`)}
              title="Experiments"
              style={{
                background: 'rgba(16,185,129,0.07)', border: '1px solid rgba(16,185,129,0.2)',
                borderRadius: 4, padding: '3px 8px', fontSize: 15, color: '#10b981',
                cursor: 'pointer', fontFamily: 'var(--font-mono)', fontWeight: 700, letterSpacing: '0.06em',
              }}
            >⚗ EXPS</button>
          </div>
        </div>

        {/* Description */}
        {project.description && (
          <p style={{ margin: '0 0 10px', color: 'var(--text-2)', fontSize: 20, lineHeight: 1.5 }}>
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
                <span style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: 3 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'rgba(255,128,21,0.6)', display: 'inline-block' }} />
                  {todo} PLANNED
                </span>
              )}
              {inProgress > 0 && (
                <span style={{ fontSize: 15, color: '#f59e0b', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: 3 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#f59e0b', display: 'inline-block' }} />
                  {inProgress} ACTIVE
                </span>
              )}
              {done > 0 && (
                <span style={{ fontSize: 15, color: '#10b981', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: 3 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
                  {done} DONE
                </span>
              )}
            </div>
          ) : (
            <span style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>NO TASKS</span>
          )}

          {/* Experiment counts */}
          {experiments.length > 0 && (
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>·</span>
              {expPlanned > 0 && (
                <span style={{ fontSize: 15, color: '#f59e0b', fontFamily: 'var(--font-mono)' }}>⚗ {expPlanned} PLANNED</span>
              )}
              {expRunning > 0 && (
                <span style={{ fontSize: 15, color: '#ff8015', fontFamily: 'var(--font-mono)' }}>⚗ {expRunning} RUNNING</span>
              )}
              {expCompleted > 0 && (
                <span style={{ fontSize: 15, color: '#10b981', fontFamily: 'var(--font-mono)' }}>⚗ {expCompleted} DONE</span>
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
                fontSize: 18, fontWeight: 700, color: '#fff',
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
            <span style={{ fontSize: 18, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginLeft: 4 }}>
              +{extraMembers}
            </span>
          )}
        </div>

        {/* Created date */}
        <span style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
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

  // Template wizard state
  const [showTemplateWizard, setShowTemplateWizard] = useState(false)
  const [templates, setTemplates] = useState<Template[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null)
  const [templateProjectName, setTemplateProjectName] = useState('')
  const [creatingFromTemplate, setCreatingFromTemplate] = useState(false)

  useEffect(() => {
    if (showTemplateWizard) {
      api.listTemplates().then(setTemplates).catch(() => {})
    }
  }, [showTemplateWizard])

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
      fontFamily: 'var(--font-mono)', fontSize: 20, letterSpacing: '0.08em',
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
          <span style={{ color: 'var(--text-dim)', fontSize: 20, fontFamily: 'var(--font-mono)' }}>/</span>
          <span style={{ color: '#ff8015', fontSize: 21, fontFamily: 'var(--font-mono)' }}>projects</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            onClick={() => navigate('/reports')}
            style={{
              background: 'rgba(255,128,21,0.08)',
              border: '1px solid rgba(255,128,21,0.18)',
              color: '#64748b',
              fontFamily: 'var(--font-mono)',
              fontSize: 16,
              padding: '5px 12px',
              borderRadius: 4,
              cursor: 'pointer',
              letterSpacing: '0.08em',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = '#ff8015'; e.currentTarget.style.borderColor = 'rgba(255,128,21,0.35)' }}
            onMouseLeave={e => { e.currentTarget.style.color = '#64748b'; e.currentTarget.style.borderColor = 'rgba(255,128,21,0.18)' }}
          >
            📊 REPORTS
          </button>
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
              fontSize: 20, fontWeight: 700, cursor: 'pointer',
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
      </div>

      {/* ── Content ── */}
      <div style={{ maxWidth: 760, margin: '0 auto', padding: '40px 28px' }}>
        <div style={{ marginBottom: 28 }}>
          <h1 style={{ margin: '0 0 5px', fontSize: 38, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>
            Research Projects
          </h1>
          <p style={{ margin: 0, fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
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
            <p style={{ color: 'var(--text-muted)', fontSize: 21, padding: '10px 0', fontStyle: 'italic' }}>
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
                borderRadius: 6, color: 'var(--text)', fontSize: 22, outline: 'none',
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
                borderRadius: 6, color: 'var(--text)', fontSize: 21, outline: 'none',
                resize: 'none', fontFamily: 'inherit',
              }}
            />
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="submit" disabled={createMutation.isPending} style={{
                padding: '8px 16px', cursor: 'pointer',
                background: '#ff8015', color: '#06091a',
                border: 'none', borderRadius: 6, fontSize: 16, fontWeight: 700,
                letterSpacing: '0.06em', fontFamily: 'var(--font-mono)',
              }}>CREATE</button>
              <button type="button" onClick={() => setCreating(false)} style={{
                padding: '8px 12px', cursor: 'pointer',
                background: 'var(--surface-input)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 6, color: 'var(--text-3)', fontSize: 21,
              }}>✕</button>
            </div>
          </form>
        ) : (
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              onClick={() => setCreating(true)}
              style={{
                padding: '9px 18px', cursor: 'pointer',
                background: 'rgba(255,128,21,0.07)',
                border: '1px solid rgba(255,128,21,0.18)',
                borderRadius: 7, color: '#ff8015',
                fontSize: 16, fontWeight: 700, letterSpacing: '0.08em',
                transition: 'background 0.14s',
                fontFamily: 'var(--font-mono)',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.13)' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.07)' }}
            >+ NEW PROJECT</button>
            <button
              onClick={() => { setShowTemplateWizard(true); setSelectedTemplate(null); setTemplateProjectName('') }}
              style={{
                padding: '9px 18px', cursor: 'pointer',
                background: 'rgba(139,92,246,0.07)',
                border: '1px solid rgba(139,92,246,0.18)',
                borderRadius: 7, color: '#a78bfa',
                fontSize: 16, fontWeight: 700, letterSpacing: '0.08em',
                transition: 'background 0.14s',
                fontFamily: 'var(--font-mono)',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(139,92,246,0.13)' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'rgba(139,92,246,0.07)' }}
            >🧬 FROM TEMPLATE</button>
          </div>
        )}
      </div>

      {/* ── Template wizard modal ── */}
      {showTemplateWizard && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 50,
          background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(6px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={() => !creatingFromTemplate && setShowTemplateWizard(false)}>
          <div
            onClick={e => e.stopPropagation()}
            style={{
              background: 'var(--surface-panel)',
              border: '1px solid var(--border)',
              borderRadius: 14, padding: '32px 36px',
              width: 580, maxHeight: '80vh', overflowY: 'auto',
              animation: 'fadeInUp 0.2s ease',
            }}
          >
            {!selectedTemplate ? (
              <>
                <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)', marginBottom: 6 }}>
                  PROJECT TEMPLATES
                </div>
                <div style={{ fontSize: 18, color: 'var(--text-dim)', marginBottom: 24 }}>
                  Choose a template to pre-populate phases, tasks, and experiment types.
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {templates.map(t => (
                    <div
                      key={t.id}
                      onClick={() => { setSelectedTemplate(t); setTemplateProjectName(t.name) }}
                      style={{
                        background: 'var(--surface-card)',
                        border: '1px solid var(--border)',
                        borderRadius: 10, padding: '16px 20px',
                        cursor: 'pointer', transition: 'border-color 0.15s, background 0.15s',
                      }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(139,92,246,0.3)'; e.currentTarget.style.background = 'var(--surface-card-hover)' }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'var(--surface-card)' }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ fontSize: 32 }}>{t.icon}</div>
                        <div>
                          <div style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-heading)' }}>{t.name}</div>
                          <div style={{ fontSize: 17, color: 'var(--text-2)', marginTop: 2 }}>{t.description}</div>
                          <div style={{ fontSize: 15, color: 'var(--text-dim)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
                            {t.phases.length} phases · {t.tasks.length} tasks · {t.experiment_types.length} experiment types
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <button
                  onClick={() => setShowTemplateWizard(false)}
                  style={{
                    marginTop: 20, padding: '9px 18px', cursor: 'pointer',
                    background: 'transparent', border: '1px solid var(--border)',
                    borderRadius: 7, color: 'var(--text-muted)',
                    fontSize: 18, fontFamily: 'var(--font-mono)',
                  }}
                >CANCEL</button>
              </>
            ) : (
              <>
                <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)', marginBottom: 10 }}>
                  {selectedTemplate.icon} {selectedTemplate.name}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 20 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>PROJECT NAME *</label>
                    <input
                      autoFocus value={templateProjectName}
                      onChange={e => setTemplateProjectName(e.target.value)}
                      placeholder="My Research Project"
                      style={{
                        padding: '9px 12px', background: 'var(--surface-input)',
                        border: '1px solid var(--border)', borderRadius: 7,
                        color: 'var(--text)', fontSize: 22, outline: 'none',
                      }}
                    />
                  </div>

                  {/* Preview */}
                  <div style={{ background: 'var(--surface-2)', borderRadius: 8, padding: 14 }}>
                    <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginBottom: 8, letterSpacing: '0.06em' }}>PHASES</div>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {selectedTemplate.phases.map(p => (
                        <span key={p.name} style={{
                          fontSize: 15, fontFamily: 'var(--font-mono)', padding: '2px 8px',
                          borderRadius: 4, background: `${p.color}18`, color: p.color,
                          border: `1px solid ${p.color}30`,
                        }}>{p.name}</span>
                      ))}
                    </div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', margin: '10px 0 6px', letterSpacing: '0.06em' }}>TASKS ({selectedTemplate.tasks.length})</div>
                    <div style={{ fontSize: 17, color: 'var(--text-2)' }}>
                      {selectedTemplate.tasks.slice(0, 4).map(t => t.title).join(' · ')}
                      {selectedTemplate.tasks.length > 4 ? ' …' : ''}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 10 }}>
                  <button
                    onClick={async () => {
                      setCreatingFromTemplate(true)
                      try {
                        await api.createProjectFromTemplate({
                          template_id: selectedTemplate.id,
                          name: templateProjectName,
                        })
                        queryClient.invalidateQueries({ queryKey: ['projects'] })
                        setShowTemplateWizard(false)
                        setSelectedTemplate(null)
                      } catch (err: unknown) {
                        alert(err instanceof Error ? err.message : 'Create failed')
                      } finally {
                        setCreatingFromTemplate(false)
                      }
                    }}
                    disabled={creatingFromTemplate || !templateProjectName.trim()}
                    style={{
                      padding: '9px 24px', cursor: 'pointer',
                      background: creatingFromTemplate ? 'rgba(139,92,246,0.07)' : 'rgba(139,92,246,0.12)',
                      border: '1px solid rgba(139,92,246,0.28)',
                      borderRadius: 7, color: '#a78bfa',
                      fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)',
                    }}
                  >{creatingFromTemplate ? 'CREATING…' : 'CREATE PROJECT'}</button>
                  <button
                    onClick={() => setSelectedTemplate(null)}
                    disabled={creatingFromTemplate}
                    style={{
                      padding: '9px 18px', cursor: 'pointer',
                      background: 'transparent', border: '1px solid var(--border)',
                      borderRadius: 7, color: 'var(--text-muted)',
                      fontSize: 18, fontFamily: 'var(--font-mono)',
                    }}
                  >BACK</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
