import React, { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { DndContext, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import type { DragStartEvent, DragOverEvent, DragEndEvent } from '@dnd-kit/core'
import { api, Task, Experiment, listPhases } from '../api'
import { TaskDetail } from './TaskDetail'
import { ExperimentDetail } from '../components/ExperimentDetail'
import { FilterToolbar } from '../components/FilterToolbar'

import { ProjectSettingsPanel } from '../components/ProjectSettingsPanel'
import { DroppableColumn } from '../components/board/DroppableColumn'
import { PhaseSwimLane } from '../components/board/PhaseSwimLane'
import { BulkActionBar } from '../components/board/BulkActionBar'
import { ResearchToolsPanel } from '../components/ResearchToolsPanel'
import { useTaskFilters } from '../hooks/useTaskFilters'
import { useAuth } from '../auth'
import { useTheme } from '../theme'

// ── Column definitions (lab context) ─────────────────────────────────────────
const COLUMNS: { key: Task['status']; label: string; accent: string; glow: string }[] = [
  { key: 'todo',        label: 'PLANNED',     accent: '#ff8015', glow: '34,211,238'  },
  { key: 'in_progress', label: 'IN PROGRESS', accent: '#f59e0b', glow: '245,158,11'  },
  { key: 'done',        label: 'COMPLETE',    accent: '#10b981', glow: '16,185,129'  },
]

const AVATAR_COLORS = ['#6366f1', '#ec4899', '#f59e0b', '#ff8015', '#10b981', '#8b5cf6']

// ── Experiment status → column key ────────────────────────────────────────────
const EXP_STATUS_TO_COL: Record<Experiment['status'], Task['status']> = {
  planned:   'todo',
  running:   'in_progress',
  completed: 'done',
  abandoned: 'todo',
}

// ── Main Board component ──────────────────────────────────────────────────────
export function Board() {
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { username, token } = useAuth()
  const { theme } = useTheme()

  const [selectedTask, setSelectedTask]   = useState<Task | null>(null)
  const [selectedExp,  setSelectedExp]    = useState<Experiment | null>(null)
  const [newTaskTitle, setNewTaskTitle]   = useState('')
  const [addingToCol,  setAddingToCol]    = useState<Task['status'] | null>(null)
  const [activeTaskId, setActiveTaskId]   = useState<string | null>(null)
  const [overColumnId, setOverColumnId]   = useState<string | null>(null)


  const [settingsPanelOpen, setSettingsPanelOpen] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [selectedExpIds, setSelectedExpIds] = useState<Set<string>>(new Set())
  const [showResearchTools, setShowResearchTools] = useState(false)
  const [showMode, setShowMode] = useState<'both' | 'tasks' | 'experiments'>('both')
  const [showExperimentsPanel, setShowExperimentsPanel] = useState(false)

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.getProject(projectId!),
    enabled: Boolean(projectId),
  })

  const isOwner = project?.members.some(m => m.username === username && m.role === 'owner') ?? false

  const { data: tasks = [] } = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => api.listTasks(projectId!),
    refetchInterval: 15_000,
    enabled: Boolean(projectId),
  })

  const { data: experiments = [] } = useQuery({
    queryKey: ['experiments', projectId],
    queryFn: () => api.listExperiments(projectId!),
    refetchInterval: 15_000,
    enabled: Boolean(projectId),
  })

  const { data: phases = [] } = useQuery({
    queryKey: ['phases', projectId],
    queryFn: () => listPhases(projectId!, token!),
    enabled: Boolean(projectId) && Boolean(token),
  })

  // ── Filter / sort ──
  const {
    search, setSearch,
    priorities, togglePriority,
    sort, setSort,
    assigneeId, setAssigneeId,
    filtered,
  } = useTaskFilters(tasks)

  // ── Create task mutation ──
  const createTask = useMutation({
    mutationFn: ({ title, status }: { title: string; status: Task['status'] }) =>
      api.createTask(projectId!, { title, status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      setNewTaskTitle('')
      setAddingToCol(null)
    },
  })

  // ── DnD status patch mutation ──
  const patchStatus = useMutation({
    mutationFn: ({ taskId, status }: { taskId: string; status: Task['status'] }) =>
      api.updateTask(projectId!, taskId, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
    },
  })

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  )

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveTaskId(String(event.active.id))
  }, [])

  const handleDragOver = useCallback((event: DragOverEvent) => {
    setOverColumnId(event.over ? String(event.over.id) : null)
  }, [])

  const patchExpStatus = useMutation({
    mutationFn: ({ expId, status }: { expId: string; status: Experiment['status'] }) =>
      api.updateExperiment(projectId!, expId, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experiments', projectId] })
    },
  })

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const activeId = String(event.active.id)
    const colKey  = event.over ? String(event.over.id) : null
    if (colKey && COLUMNS.some(c => c.key === colKey)) {
      if (activeId.startsWith('exp-')) {
        // Experiment drag → update experiment status
        const expId = activeId.slice(4)
        const exp = experiments.find(e => String(e.id) === expId)
        const targetStatus = (Object.entries(EXP_STATUS_TO_COL) as [Experiment['status'], Task['status']][])
          .find(([, col]) => col === colKey)?.[0]
        if (exp && targetStatus && exp.status !== targetStatus) {
          patchExpStatus.mutate({ expId, status: targetStatus })
        }
      } else {
        // Task drag → update task status
        const task = tasks.find(t => String(t.id) === activeId)
        if (task && task.status !== colKey) {
          patchStatus.mutate({ taskId: activeId, status: colKey as Task['status'] })
        }
      }
    }
    setActiveTaskId(null)
    setOverColumnId(null)
  }, [tasks, experiments, patchStatus, patchExpStatus])

  const handleAddSubmit = useCallback((colKey: Task['status']) => (title: string) => {
    createTask.mutate({ title, status: colKey })
  }, [createTask])

  const handleAddCancel = useCallback(() => setAddingToCol(null), [])

  const handleCardClick = useCallback((task: Task) => setSelectedTask(task), [])
  const handleExpClick  = useCallback((exp: Experiment) => setSelectedExp(exp), [])

  const toggleSelect = useCallback((taskId: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      next.has(taskId) ? next.delete(taskId) : next.add(taskId)
      return next
    })
  }, [])

  const toggleExpSelect = useCallback((expId: string) => {
    setSelectedExpIds(prev => {
      const next = new Set(prev)
      next.has(expId) ? next.delete(expId) : next.add(expId)
      return next
    })
  }, [])

  const applyBulkUpdate = useCallback(async (updates: Partial<Task>) => {
    await Promise.all(
      [...selectedIds].map(id => api.updateTask(projectId!, id, updates))
    )
    queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
    setSelectedIds(new Set())
  }, [selectedIds, projectId, queryClient])

  const applyBulkExpUpdate = useCallback(async (updates: Partial<Experiment>) => {
    await Promise.all(
      [...selectedExpIds].map(id => api.updateExperiment(projectId!, id, updates))
    )
    queryClient.invalidateQueries({ queryKey: ['experiments', projectId] })
    setSelectedExpIds(new Set())
  }, [selectedExpIds, projectId, queryClient])

  // ── Keyboard shortcuts ────────────────────────────────────────────────
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement
      const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable
      if (isInput) return
      if (e.key === 'n' || e.key === 'N') setAddingToCol('todo')
      if (e.key === 'Escape') { setSelectedTask(null); setSelectedExp(null); setAddingToCol(null) }
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); /* search — handled by browser */ }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [])

  return (
    <div style={{ background: 'var(--bg)', height: '100vh', display: 'flex', flexDirection: 'column', color: 'var(--text)' }}>

      {/* ── Header row 1: project name + avatars ── */}
      <div style={{
        padding: '0 24px', height: 52,
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 14,
        background: 'var(--surface-header)',
        backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 10,
        flexShrink: 0,
      }}>
        <button
          onClick={() => navigate('/projects')}
          style={{
            cursor: 'pointer',
            background: 'var(--surface-input)',
            border: '1px solid var(--border)',
            borderRadius: 6, color: 'var(--text-muted)',
            padding: '3px 9px', fontSize: 22, lineHeight: 1,
            transition: 'color 0.15s, border-color 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.color = '#ff8015'; e.currentTarget.style.borderColor = 'rgba(255,128,21,0.3)' }}
          onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.borderColor = 'var(--border)' }}
        >←</button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: '#ff8015', boxShadow: '0 0 6px #ff8015',
            flexShrink: 0,
          }} />
          <h1 style={{
            margin: 0, fontSize: 21, fontWeight: 600,
            letterSpacing: '0.03em', color: 'var(--text-heading)',
            fontFamily: 'var(--font-mono)',
          }}>
            {project?.name ?? '…'} — Kanban Board
          </h1>
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            onClick={() => setShowExperimentsPanel(o => !o)}
            style={{
              background: showExperimentsPanel ? 'rgba(16,185,129,0.15)' : 'rgba(16,185,129,0.08)',
              border: showExperimentsPanel ? '1px solid rgba(16,185,129,0.35)' : '1px solid rgba(16,185,129,0.18)',
              color: showExperimentsPanel ? '#10b981' : '#64748b',
              fontFamily: 'var(--font-mono)',
              fontSize: 20,
              padding: '4px 10px',
              borderRadius: 4,
              cursor: 'pointer',
              letterSpacing: '0.08em',
            }}
            onMouseEnter={e => { if (!showExperimentsPanel) { e.currentTarget.style.color = '#10b981'; e.currentTarget.style.borderColor = 'rgba(16,185,129,0.35)' } }}
            onMouseLeave={e => { if (!showExperimentsPanel) { e.currentTarget.style.color = '#64748b'; e.currentTarget.style.borderColor = 'rgba(16,185,129,0.18)' } }}
          >
            ⚗ EXPERIMENTS
          </button>
          <button
            onClick={() => navigate(`/projects/${projectId}/report`)}
            style={{
              background: 'rgba(255,128,21,0.08)',
              border: '1px solid rgba(255,128,21,0.18)',
              color: '#64748b',
              fontFamily: 'var(--font-mono)',
              fontSize: 20,
              padding: '4px 10px',
              borderRadius: 4,
              cursor: 'pointer',
              letterSpacing: '0.08em',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = '#ff8015'; e.currentTarget.style.borderColor = 'rgba(255,128,21,0.35)' }}
            onMouseLeave={e => { e.currentTarget.style.color = '#64748b'; e.currentTarget.style.borderColor = 'rgba(255,128,21,0.18)' }}
          >
            📊 REPORT
          </button>
          <button
            onClick={() => setShowMode(m => m === 'both' ? 'tasks' : m === 'tasks' ? 'experiments' : 'both')}
            title="Toggle board view: tasks / experiments / both"
            style={{
              background: showMode === 'both' ? 'rgba(16,185,129,0.12)' : 'rgba(16,185,129,0.06)',
              border: '1px solid rgba(16,185,129,0.3)',
              color: showMode === 'both' ? '#10b981' : '#64748b',
              fontFamily: 'var(--font-mono)',
              fontSize: 16,
              padding: '5px 12px',
              borderRadius: 4,
              cursor: 'pointer',
              letterSpacing: '0.08em',
            }}
          >
            {showMode === 'both' ? '⚗ BOTH' : showMode === 'tasks' ? '📋 TASKS' : '🔬 EXPS'}
          </button>

          {isOwner && (
            <button
              onClick={() => setSettingsPanelOpen(true)}
              style={{
                background: 'var(--surface-input)',
                border: '1px solid var(--border)',
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
                fontSize: 20,
                padding: '4px 10px',
                borderRadius: 4,
                cursor: 'pointer',
                letterSpacing: '0.08em',
              }}
            >
              ⚙ SETTINGS
            </button>
          )}
          <div style={{ display: 'flex', gap: 5 }}>
            {project?.members.map((m, i) => (
              <span
                key={m.user_id}
                title={`${m.username} (${m.role})`}
                style={{
                  width: 26, height: 26, borderRadius: '50%',
                  background: AVATAR_COLORS[i % AVATAR_COLORS.length],
                  color: '#fff', display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontSize: 16, fontWeight: 700,
                  border: '2px solid var(--bg)',
                  fontFamily: 'var(--font-mono)',
                  cursor: 'default',
                }}>
                {m.username[0].toUpperCase()}
              </span>
            ))}
          </div>
          <button
            onClick={() => navigate('/profile')}
            title={username ?? 'Profile'}
            style={{
              width: 28, height: 28, borderRadius: '50%', border: 'none',
              background: theme === 'dark'
                ? 'linear-gradient(135deg, rgba(255,128,21,0.25), rgba(139,92,246,0.25))'
                : 'linear-gradient(135deg, rgba(255,128,21,0.4), rgba(139,92,246,0.4))',
              color: '#ff8015',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 16, fontWeight: 700, cursor: 'pointer',
              fontFamily: 'var(--font-mono)',
              outline: '1px solid rgba(255,128,21,0.25)',
              transition: 'outline-color 0.15s, box-shadow 0.15s',
              flexShrink: 0,
            }}
            onMouseEnter={e => { e.currentTarget.style.outlineColor = 'rgba(255,128,21,0.6)'; e.currentTarget.style.boxShadow = '0 0 10px rgba(255,128,21,0.2)' }}
            onMouseLeave={e => { e.currentTarget.style.outlineColor = 'rgba(255,128,21,0.25)'; e.currentTarget.style.boxShadow = '' }}
          >
            {username?.[0]?.toUpperCase() ?? '?'}
          </button>
        </div>
      </div>

      {/* ── Header row 2: filter toolbar ── */}
      <div style={{
        padding: '0 24px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--surface-header)',
        backdropFilter: 'blur(12px)',
        position: 'sticky', top: 52, zIndex: 9,
        flexShrink: 0,
      }}>
        <FilterToolbar
          search={search}
          onSearchChange={setSearch}
          priorities={priorities}
          onTogglePriority={togglePriority}
          sort={sort}
          onSortChange={setSort}
          assigneeId={assigneeId}
          onAssigneeChange={setAssigneeId}
          members={project?.members ?? []}
        />
      </div>

      {/* ── Columns / Swimlanes ── */}
      <DndContext
        sensors={sensors}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
        {phases.length === 0 ? (
          /* Original flat kanban (no phases) */
          <div style={{
            display: 'flex', flex: 1, overflowX: 'auto',
            padding: '20px 20px', gap: 16,
            alignItems: 'flex-start',
          }}>
            {COLUMNS.map(col => {
              const colTasks = (showMode !== 'experiments' ? filtered : []).filter(t => t.status === col.key)
              const colExps  = (showMode !== 'tasks' ? experiments : []).filter(e => EXP_STATUS_TO_COL[e.status] === col.key)
              return (
                <DroppableColumn
                  key={col.key}
                  col={col}
                  colTasks={colTasks}
                  colExps={colExps}
                  isDropTarget={overColumnId === col.key}
                  activeTaskId={activeTaskId}
                  addingToCol={addingToCol}
                  newTaskTitle={newTaskTitle}
                  onNewTaskTitleChange={setNewTaskTitle}
                  onAddStart={setAddingToCol}
                  onAddCancel={handleAddCancel}
                  onAddSubmit={handleAddSubmit(col.key)}
                  onCardClick={handleCardClick}
                  onExpClick={handleExpClick}
                  members={project?.members ?? []}
                  selectedIds={selectedIds}
                  onToggleSelect={toggleSelect}
                  selectedExpIds={selectedExpIds}
                  onToggleExpSelect={toggleExpSelect}
                />
              )
            })}
          </div>
        ) : (
          /* Phase swimlanes */
          <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
            {/* Column header row (sticky) */}
            <div style={{
              display: 'flex',
              position: 'sticky', top: 0, zIndex: 5,
              background: 'var(--surface-header)',
              borderBottom: '1px solid var(--border)',
              backdropFilter: 'blur(12px)',
            }}>
              <div style={{ width: 120, flexShrink: 0, borderRight: '1px solid var(--border-subtle)' }} />
              <div style={{ display: 'flex', flex: 1, gap: 16, padding: '8px 16px' }}>
                {COLUMNS.map(col => (
                  <div key={col.key} style={{
                    flex: '0 0 290px',
                    fontSize: 15, fontWeight: 700,
                    letterSpacing: '0.12em', textTransform: 'uppercase',
                    color: col.accent, fontFamily: 'var(--font-mono)',
                    padding: '4px 0',
                  }}>
                    {col.label}
                  </div>
                ))}
              </div>
            </div>

            {/* One swimlane per phase */}
            {phases.map(phase => {
              const laneTasks = (showMode !== 'experiments' ? filtered : []).filter(t => t.phase_id === phase.id)
              const laneExps  = (showMode !== 'tasks' ? experiments : []).filter(e => e.phase_id === phase.id)
              return (
                <PhaseSwimLane
                  key={phase.id}
                  phase={phase}
                  tasks={laneTasks}
                  experiments={laneExps}
                  overColumnId={overColumnId}
                  activeTaskId={activeTaskId}
                  addingToCol={addingToCol}
                  newTaskTitle={newTaskTitle}
                  onNewTaskTitleChange={setNewTaskTitle}
                  onAddStart={setAddingToCol}
                  onAddCancel={handleAddCancel}
                  onAddSubmit={handleAddSubmit}
                  onCardClick={handleCardClick}

                  onExpClick={handleExpClick}
                  members={project?.members ?? []}
                  selectedIds={selectedIds}
                  onToggleSelect={toggleSelect}
                  selectedExpIds={selectedExpIds}
                  onToggleExpSelect={toggleExpSelect}
                />
              )
            })}

            {/* Unassigned swimlane */}
            {(() => {
              const phaseIds = new Set(phases.map(p => p.id))
              const unassignedTasks = (showMode !== 'experiments' ? filtered : []).filter(t => !t.phase_id || !phaseIds.has(t.phase_id))
              const unassignedExps  = (showMode !== 'tasks' ? experiments : []).filter(e => !e.phase_id || !phaseIds.has(e.phase_id))
              return (
                <PhaseSwimLane
                  key="unassigned"
                  phase={null}
                  tasks={unassignedTasks}
                  experiments={unassignedExps}
                  overColumnId={overColumnId}
                  activeTaskId={activeTaskId}
                  addingToCol={addingToCol}
                  newTaskTitle={newTaskTitle}
                  onNewTaskTitleChange={setNewTaskTitle}
                  onAddStart={setAddingToCol}
                  onAddCancel={handleAddCancel}
                  onAddSubmit={handleAddSubmit}
                  onCardClick={handleCardClick}

                  onExpClick={handleExpClick}
                  members={project?.members ?? []}
                  selectedIds={selectedIds}
                  onToggleSelect={toggleSelect}
                  selectedExpIds={selectedExpIds}
                  onToggleExpSelect={toggleExpSelect}
                />
              )
            })()}
          </div>
        )}
      </DndContext>

      {selectedTask && (
        <TaskDetail
          key={selectedTask.id}
          task={selectedTask}
          projectId={projectId!}
          onClose={() => setSelectedTask(null)}
          members={project?.members ?? []}
        />
      )}

      {selectedExp && (
        <ExperimentDetail
          key={selectedExp.id}
          experiment={selectedExp}
          projectId={projectId!}
          onClose={() => setSelectedExp(null)}
          phases={phases}
        />
      )}

      {showExperimentsPanel && (
        <div style={{
          position: 'fixed', right: 0, top: 100, bottom: 0, width: 380,
          background: 'var(--surface-panel)', borderLeft: '1px solid var(--border)',
          zIndex: 40, display: 'flex', flexDirection: 'column',
          animation: 'slideIn 0.2s ease',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 16px', borderBottom: '1px solid var(--border)',
          }}>
            <span style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#10b981' }}>
              ⚗ Experiments
            </span>
            <button onClick={() => setShowExperimentsPanel(false)} style={{
              background: 'none', border: 'none', cursor: 'pointer', fontSize: 20,
              color: 'var(--text-dim)', padding: '2px 6px', borderRadius: 4,
            }}>✕</button>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
            {experiments.length === 0 ? (
              <div style={{ color: 'var(--text-dim)', fontSize: 14, padding: 16, textAlign: 'center' }}>
                No experiments yet.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {experiments.map(exp => {
                  const statusColor = exp.status === 'completed' ? '#10b981' : exp.status === 'running' ? '#f59e0b' : exp.status === 'planned' ? '#ff8015' : '#6b7280'
                  return (
                    <div key={exp.id} onClick={() => handleExpClick(exp)} style={{
                      cursor: 'pointer', padding: '12px 14px',
                      background: 'var(--surface-card)', border: '1px solid var(--border)',
                      borderLeft: `3px solid ${statusColor}`,
                      borderRadius: 8, transition: 'border-color 0.14s',
                    }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = `rgba(16,185,129,0.25)` }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
                        <span style={{ fontSize: 17, fontWeight: 600, color: 'var(--text-heading)', lineHeight: 1.3 }}>{exp.name}</span>
                        <span style={{
                          fontSize: 11, fontWeight: 700, fontFamily: 'var(--font-mono)',
                          color: statusColor, background: `${statusColor}14`,
                          border: `1px solid ${statusColor}30`, borderRadius: 3, padding: '1px 5px', whiteSpace: 'nowrap', marginLeft: 6,
                        }}>{exp.status.toUpperCase()}</span>
                      </div>
                      {exp.hypothesis && (
                        <div style={{ fontSize: 15, color: 'var(--text-dim)', lineHeight: 1.4, fontStyle: 'italic', marginTop: 2 }}>
                          {exp.hypothesis.slice(0, 120)}{exp.hypothesis.length > 120 ? '…' : ''}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}
      <style>{`@keyframes slideIn { from { transform: translateX(20px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }`}</style>

      {showResearchTools && projectId && (
        <ResearchToolsPanel projectId={projectId} onClose={() => setShowResearchTools(false)} />
      )}
      {settingsPanelOpen && project && (
        <ProjectSettingsPanel
          project={project}
          projectId={projectId!}
          onClose={() => setSettingsPanelOpen(false)}
        />
      )}

      {selectedIds.size > 0 && (
        <BulkActionBar
          count={selectedIds.size}
          label="tasks"
          phases={phases}
          statusOptions={[
            { value: 'todo', label: 'PLANNED' },
            { value: 'in_progress', label: 'IN PROGRESS' },
            { value: 'done', label: 'COMPLETE' },
          ]}
          onStatusChange={status => applyBulkUpdate({ status: status as Task['status'] })}
          onPhaseChange={phaseId => applyBulkUpdate({ phase_id: phaseId as Task['phase_id'] })}
          onClear={() => setSelectedIds(new Set())}
        />
      )}
      {selectedExpIds.size > 0 && (
        <BulkActionBar
          count={selectedExpIds.size}
          label="experiments"
          phases={phases}
          statusOptions={[
            { value: 'planned', label: 'PLANNED' },
            { value: 'running', label: 'RUNNING' },
            { value: 'completed', label: 'COMPLETED' },
            { value: 'abandoned', label: 'ABANDONED' },
          ]}
          onStatusChange={status => applyBulkExpUpdate({ status: status as Experiment['status'] })}
          onPhaseChange={phaseId => applyBulkExpUpdate({ phase_id: phaseId as Experiment['phase_id'] })}
          onClear={() => setSelectedExpIds(new Set())}
        />
      )}
    </div>
  )
}
