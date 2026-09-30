import React, { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { DndContext, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import type { DragStartEvent, DragOverEvent, DragEndEvent } from '@dnd-kit/core'
import { api, Task, Experiment, listPhases } from '../api'
import { TaskDetail } from './TaskDetail'
import { ExperimentDetail } from '../components/ExperimentDetail'
import { NewExperimentDialog } from '../components/experiment/NewExperimentDialog'
import { FilterToolbar } from '../components/FilterToolbar'

import { ProjectSettingsPanel } from '../components/ProjectSettingsPanel'
import { DroppableColumn } from '../components/board/DroppableColumn'
import { PhaseSwimLane } from '../components/board/PhaseSwimLane'
import { BulkActionBar } from '../components/board/BulkActionBar'
import { ResearchToolsPanel } from '../components/ResearchToolsPanel'
import { useTaskFilters } from '../hooks/useTaskFilters'
import { useAuth } from '../auth'
import { ProjectHeader } from '../components/ProjectHeader'

// ── Column definitions (lab context) ─────────────────────────────────────────
const COLUMNS: { key: Task['status']; label: string; accent: string; glow: string }[] = [
  { key: 'todo',        label: 'Planned',     accent: '#ff8015', glow: '34,211,238'  },
  { key: 'in_progress', label: 'In progress', accent: '#f59e0b', glow: '245,158,11'  },
  { key: 'done',        label: 'Complete',    accent: '#10b981', glow: '16,185,129'  },
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
  const [showNewExperiment, setShowNewExperiment] = useState(false)

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

      <ProjectHeader projectId={projectId!} name={project?.name} actions={<>
        <div className="seg" role="group" aria-label="Show on board">
          {(['tasks', 'experiments', 'both'] as const).map(m => (
            <button key={m} aria-pressed={showMode === m} onClick={() => setShowMode(m)}>
              {m === 'tasks' ? 'Tasks' : m === 'experiments' ? 'Experiments' : 'Both'}
            </button>
          ))}
        </div>
        <button className="btn" onClick={() => setShowResearchTools(o => !o)}>✦ AI tools</button>
        <button className="btn" aria-pressed={showExperimentsPanel} onClick={() => setShowExperimentsPanel(o => !o)}>
          {showExperimentsPanel ? 'Hide' : 'Show'} experiment panel
        </button>
        {isOwner && <button className="btn" onClick={() => setSettingsPanelOpen(true)}>⚙ Settings</button>}
        <div style={{ display: 'flex', alignItems: 'center' }}>
          {project?.members.map((m, i) => (
            <span key={m.user_id} title={`${m.username} (${m.role})`} style={{
              width: 26, height: 26, borderRadius: '50%', marginLeft: i ? -6 : 0,
              background: AVATAR_COLORS[i % AVATAR_COLORS.length], color: '#fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 12, fontWeight: 700, border: '2px solid var(--surface)',
            }}>{m.username[0].toUpperCase()}</span>
          ))}
        </div>
      </>} />

      {/* ── Header row 2: filter toolbar ── */}
      <div style={{
        padding: '0 24px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--surface-header)',
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
                    letterSpacing: '0.04em', textTransform: 'uppercase',
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

      {showNewExperiment && projectId && (
        <NewExperimentDialog
          projectId={projectId}
          phases={phases}
          onCreated={exp => { setShowNewExperiment(false); setSelectedExp(exp) }}
          onClose={() => setShowNewExperiment(false)}
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
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              {/* The panel could list experiments but not make one, so creating
                  from the board meant leaving for the experiments page. */}
              <button
                onClick={() => setShowNewExperiment(true)}
                title="New experiment"
                style={{
                  background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.28)',
                  borderRadius: 4, padding: '2px 9px', color: '#10b981',
                  fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)',
                  letterSpacing: '0.04em', cursor: 'pointer',
                }}
              >+ New</button>
              <button onClick={() => setShowExperimentsPanel(false)} style={{
                background: 'none', border: 'none', cursor: 'pointer', fontSize: 16,
                color: 'var(--text-dim)', padding: '2px 6px', borderRadius: 4,
              }}>✕</button>
            </div>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
            {experiments.length === 0 ? (
              <div style={{ color: 'var(--text-dim)', fontSize: 14, padding: 16, textAlign: 'center' }}>
                <div>No experiments yet.</div>
                <button
                  onClick={() => setShowNewExperiment(true)}
                  style={{
                    marginTop: 10, background: 'rgba(16,185,129,0.1)',
                    border: '1px solid rgba(16,185,129,0.28)', borderRadius: 4,
                    padding: '5px 14px', color: '#10b981', fontSize: 15,
                    fontWeight: 700, fontFamily: 'var(--font-mono)', cursor: 'pointer',
                  }}
                >+ New experiment</button>
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
                        <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-heading)', lineHeight: 1.3 }}>{exp.name}</span>
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
            { value: 'todo', label: 'Planned' },
            { value: 'in_progress', label: 'In progress' },
            { value: 'done', label: 'Complete' },
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
            { value: 'planned', label: 'Planned' },
            { value: 'running', label: 'Running' },
            { value: 'completed', label: 'Completed' },
            { value: 'abandoned', label: 'Abandoned' },
          ]}
          onStatusChange={status => applyBulkExpUpdate({ status: status as Experiment['status'] })}
          onPhaseChange={phaseId => applyBulkExpUpdate({ phase_id: phaseId as Experiment['phase_id'] })}
          onClear={() => setSelectedExpIds(new Set())}
        />
      )}
    </div>
  )
}
