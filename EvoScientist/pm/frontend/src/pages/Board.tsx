import React, { useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { DndContext, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import type { DragStartEvent, DragOverEvent, DragEndEvent } from '@dnd-kit/core'
import { useDraggable, useDroppable } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import { api, Task, Experiment } from '../api'
import { TaskDetail } from './TaskDetail'
import { ExperimentDetail } from '../components/ExperimentDetail'
import { FilterToolbar } from '../components/FilterToolbar'
import { CardEditPopover } from '../components/CardEditPopover'
import { ProjectSettingsPanel } from '../components/ProjectSettingsPanel'
import { useTaskFilters } from '../hooks/useTaskFilters'
import { useAuth } from '../auth'
import { useTheme } from '../theme'

// ── Column definitions (lab context) ─────────────────────────────────────────
const COLUMNS: { key: Task['status']; label: string; accent: string; glow: string }[] = [
  { key: 'todo',        label: 'PLANNED',     accent: '#ff8015', glow: '34,211,238'  },
  { key: 'in_progress', label: 'IN PROGRESS', accent: '#f59e0b', glow: '245,158,11'  },
  { key: 'done',        label: 'COMPLETE',    accent: '#10b981', glow: '16,185,129'  },
]

// ── Priority labels / colors (lab terminology) ────────────────────────────────
const PRIORITY: Record<string, { color: string; label: string }> = {
  high:   { color: '#f43f5e', label: 'CRIT' },
  medium: { color: '#f59e0b', label: 'NORM' },
  low:    { color: '#10b981', label: 'ROUT' },
}

const AVATAR_COLORS = ['#6366f1', '#ec4899', '#f59e0b', '#ff8015', '#10b981', '#8b5cf6']

// ── Overdue helper ────────────────────────────────────────────────────────────
function isOverdue(task: Task): boolean {
  return Boolean(task.deadline) && new Date(task.deadline!) < new Date()
}

// ── Experiment status → column key ────────────────────────────────────────────
const EXP_STATUS_TO_COL: Record<Experiment['status'], Task['status']> = {
  planned:   'todo',
  running:   'in_progress',
  completed: 'done',
}

// ── Draggable task card ───────────────────────────────────────────────────────
interface DraggableCardProps {
  task: Task
  col: typeof COLUMNS[number]
  idx: number
  activeTaskId: string | null
  onCardClick: (task: Task) => void
  onEditClick: (task: Task, rect: DOMRect) => void
  members: { user_id: string; username: string }[]
}

function DraggableCard({ task, col, idx, activeTaskId, onCardClick, onEditClick, members }: DraggableCardProps) {
  const [isHovered, setIsHovered] = useState(false)
  const { attributes, listeners, setNodeRef, transform } = useDraggable({ id: String(task.id) })

  const p = PRIORITY[task.priority] ?? PRIORITY.low
  const overdue = isOverdue(task)
  const isDragging = activeTaskId === String(task.id)

  const assignee = task.assignee_id ? members.find(m => m.user_id === task.assignee_id) : null
  const descSnippet = task.description ? task.description.slice(0, 60) + (task.description.length > 60 ? '…' : '') : null

  const cardStyle: React.CSSProperties = {
    background: 'var(--surface-card)',
    border: '1px solid var(--border-subtle)',
    borderLeft: overdue ? '3px solid #f43f5e' : undefined,
    borderRadius: 7,
    padding: '11px 13px',
    cursor: 'pointer',
    transition: 'transform 0.14s, border-color 0.14s, box-shadow 0.14s',
    animation: 'fadeInUp 0.22s ease both',
    animationDelay: `${idx * 0.035}s`,
    opacity: isDragging ? 0.35 : 1,
    position: 'relative',
    transform: CSS.Transform.toString(transform) ?? undefined,
  }

  return (
    <div
      ref={setNodeRef}
      data-card="true"
      style={cardStyle}
      {...listeners}
      {...attributes}
      onClick={() => onCardClick(task)}
      onMouseEnter={e => {
        setIsHovered(true)
        const el = e.currentTarget
        el.style.transform = CSS.Transform.toString(transform) ? CSS.Transform.toString(transform)! : 'translateY(-2px)'
        el.style.borderColor = overdue ? '#f43f5e' : `rgba(${col.glow},0.3)`
        el.style.boxShadow = `0 5px 18px rgba(0,0,0,0.28), 0 0 0 1px rgba(${col.glow},0.12)`
      }}
      onMouseLeave={e => {
        setIsHovered(false)
        const el = e.currentTarget
        el.style.transform = CSS.Transform.toString(transform) ?? ''
        el.style.borderColor = overdue ? '#f43f5e' : 'var(--border-subtle)'
        el.style.boxShadow = ''
      }}
    >
      {/* Edit icon (shown on hover) */}
      {isHovered && (
        <button
          title="Edit"
          onPointerDown={e => e.stopPropagation()}
          onClick={e => {
            e.stopPropagation()
            const card = e.currentTarget.closest<HTMLElement>('[data-card]')
            if (!card) return
            onEditClick(task, card.getBoundingClientRect())
          }}
          style={{
            position: 'absolute',
            top: 6,
            right: 8,
            background: 'rgba(255,128,21,0.1)',
            border: '1px solid rgba(255,128,21,0.22)',
            borderRadius: 4,
            color: '#ff8015',
            cursor: 'pointer',
            fontSize: 13,
            lineHeight: 1,
            padding: '2px 5px',
            zIndex: 2,
          }}
        >
          ✎
        </button>
      )}

      <p style={{ margin: '0 0 6px', fontWeight: 500, fontSize: 15, lineHeight: 1.4, color: 'var(--text-heading)' }}>
        {task.title}
      </p>

      {descSnippet && (
        <p style={{ margin: '0 0 8px', fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.4 }}>
          {descSnippet}
        </p>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{
          width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
          background: p.color, boxShadow: `0 0 5px ${p.color}88`,
        }} />
        <span style={{
          fontSize: 10, fontWeight: 700, color: p.color,
          letterSpacing: '0.1em', fontFamily: 'var(--font-mono)',
        }}>
          {p.label}
        </span>
        {assignee && (
          <span
            title={assignee.username}
            style={{
              width: 18, height: 18, borderRadius: '50%',
              background: 'rgba(255,128,21,0.18)',
              border: '1px solid rgba(255,128,21,0.3)',
              color: '#ff8015', fontSize: 10, fontWeight: 700,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--font-mono)', flexShrink: 0,
            }}
          >
            {assignee.username[0].toUpperCase()}
          </span>
        )}
        {task.deadline && (
          <span style={{
            marginLeft: 'auto', fontSize: 10,
            color: overdue ? '#f43f5e' : 'var(--text-dim)',
            fontFamily: 'var(--font-mono)',
          }}>
            Due {task.deadline}
          </span>
        )}
      </div>
    </div>
  )
}

// ── Experiment card (non-draggable) ───────────────────────────────────────────
const EXP_ACCENT = '#10b981'
const EXP_GLOW   = '16,185,129'

interface ExperimentCardProps {
  exp: Experiment
  idx: number
  onExpClick: (exp: Experiment) => void
}

function ExperimentCard({ exp, idx, onExpClick }: ExperimentCardProps) {
  const [hovered, setHovered] = useState(false)
  const hypoSnippet = exp.hypothesis ? exp.hypothesis.slice(0, 70) + (exp.hypothesis.length > 70 ? '…' : '') : null

  return (
    <div
      onClick={() => onExpClick(exp)}
      style={{
        background: hovered ? `rgba(${EXP_GLOW},0.06)` : 'var(--surface-card)',
        border: `1px solid ${hovered ? `rgba(${EXP_GLOW},0.3)` : `rgba(${EXP_GLOW},0.18)`}`,
        borderLeft: `3px solid ${EXP_ACCENT}`,
        borderRadius: 7,
        padding: '10px 13px',
        cursor: 'pointer',
        animation: 'fadeInUp 0.22s ease both',
        animationDelay: `${idx * 0.035}s`,
        transition: 'background 0.14s, border-color 0.14s, box-shadow 0.14s',
        boxShadow: hovered ? `0 5px 18px rgba(0,0,0,0.22), 0 0 0 1px rgba(${EXP_GLOW},0.1)` : undefined,
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 6 }}>
        <span style={{
          fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)',
          letterSpacing: '0.08em', color: EXP_ACCENT,
          background: `rgba(${EXP_GLOW},0.1)`,
          border: `1px solid rgba(${EXP_GLOW},0.25)`,
          borderRadius: 3, padding: '1px 5px',
        }}>
          ⚗ EXP
        </span>
        {exp.tags.slice(0, 2).map(tag => (
          <span key={tag} style={{
            fontSize: 12, fontFamily: 'var(--font-mono)',
            color: 'var(--text-dim)',
            background: 'var(--surface-2)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 3, padding: '1px 4px',
          }}>{tag}</span>
        ))}
      </div>

      <p style={{ margin: '0 0 5px', fontWeight: 500, fontSize: 14, lineHeight: 1.4, color: 'var(--text-heading)' }}>
        {exp.name}
      </p>

      {hypoSnippet && (
        <p style={{ margin: '0 0 6px', fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.4, fontStyle: 'italic' }}>
          {hypoSnippet}
        </p>
      )}

      {exp.deadline && (
        <div style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
          Due {exp.deadline}
        </div>
      )}
    </div>
  )
}

// ── Droppable column ──────────────────────────────────────────────────────────
interface DroppableColumnProps {
  col: typeof COLUMNS[number]
  colTasks: Task[]
  colExps: Experiment[]
  isDropTarget: boolean
  activeTaskId: string | null
  addingToCol: Task['status'] | null
  newTaskTitle: string
  onNewTaskTitleChange: (v: string) => void
  onAddStart: (status: Task['status']) => void
  onAddCancel: () => void
  onAddSubmit: (title: string) => void
  onCardClick: (task: Task) => void
  onEditClick: (task: Task, rect: DOMRect) => void
  onExpClick: (exp: Experiment) => void
  members: { user_id: string; username: string }[]
}

function DroppableColumn({
  col, colTasks, colExps, isDropTarget, activeTaskId,
  addingToCol, newTaskTitle, onNewTaskTitleChange,
  onAddStart, onAddCancel, onAddSubmit,
  onCardClick, onEditClick, onExpClick, members,
}: DroppableColumnProps) {
  const { setNodeRef } = useDroppable({ id: col.key })

  const columnStyle: React.CSSProperties = {
    flex: '0 0 290px',
    background: isDropTarget ? `rgba(${col.glow},0.07)` : 'var(--surface-2)',
    border: isDropTarget
      ? `2px solid ${col.accent}`
      : '1px solid var(--border-subtle)',
    boxShadow: isDropTarget ? `0 0 14px rgba(${col.glow},0.25)` : undefined,
    borderTop: `2px solid ${col.accent}`,
    borderRadius: '0 0 10px 10px',
    display: 'flex',
    flexDirection: 'column',
    maxHeight: 'calc(100vh - 148px)',
    overflow: 'hidden',
    transition: 'background 0.15s, border 0.15s, box-shadow 0.15s',
  }

  const dimBg = `rgba(${col.glow},0.04)`

  return (
    <div ref={setNodeRef} style={columnStyle}>
      {/* Column header */}
      <div style={{
        padding: '11px 13px 9px',
        background: dimBg,
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        flexShrink: 0,
      }}>
        <span style={{
          fontSize: 11, fontWeight: 700,
          letterSpacing: '0.12em', textTransform: 'uppercase',
          color: col.accent, fontFamily: 'var(--font-mono)',
        }}>
          {col.label}
        </span>
        <span style={{
          fontSize: 11, fontWeight: 700,
          color: col.accent,
          background: `rgba(${col.glow},0.1)`,
          border: `1px solid rgba(${col.glow},0.22)`,
          borderRadius: 9, padding: '1px 7px',
          fontFamily: 'var(--font-mono)',
        }}>
          {col.label} · {colTasks.length + colExps.length}
        </span>
      </div>

      {/* Cards */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 9px 4px', display: 'flex', flexDirection: 'column', gap: 7 }}>
        {colExps.map((exp, idx) => (
          <ExperimentCard
            key={`exp-${exp.id}`}
            exp={exp}
            idx={idx}
            onExpClick={onExpClick}
          />
        ))}
        {colTasks.map((task, idx) => (
          <DraggableCard
            key={task.id}
            task={task}
            col={col}
            idx={colExps.length + idx}
            activeTaskId={activeTaskId}
            onCardClick={onCardClick}
            onEditClick={onEditClick}
            members={members}
          />
        ))}

        {/* Drop ghost placeholder */}
        {isDropTarget && activeTaskId && (
          <div style={{
            height: 80,
            border: `1px dashed ${col.accent}`,
            borderRadius: 6,
            margin: '4px 0',
            opacity: 0.5,
          }} />
        )}
      </div>

      {/* Add experiment footer */}
      <div style={{ padding: '6px 9px 9px', flexShrink: 0 }}>
        {addingToCol === col.key ? (
          <form onSubmit={e => { e.preventDefault(); onAddSubmit(newTaskTitle) }}>
            <input
              autoFocus
              value={newTaskTitle}
              onChange={e => onNewTaskTitleChange(e.target.value)}
              placeholder="Task title…"
              required
              style={{
                width: '100%', padding: '7px 10px', boxSizing: 'border-box', marginBottom: 5,
                background: 'var(--surface-input)',
                border: `1px solid rgba(${col.glow},0.3)`,
                borderRadius: 6, color: 'var(--text)', fontSize: 14, outline: 'none',
              }}
            />
            <div style={{ display: 'flex', gap: 4 }}>
              <button type="submit" style={{
                flex: 1, padding: '5px 0', fontSize: 13, cursor: 'pointer',
                background: col.accent, color: '#070b12',
                border: 'none', borderRadius: 5, fontWeight: 700,
                fontFamily: 'var(--font-mono)',
              }}>
                ADD
              </button>
              <button type="button" onClick={onAddCancel} style={{
                padding: '5px 9px', fontSize: 13, cursor: 'pointer',
                background: 'var(--surface-input)',
                border: '1px solid var(--border)',
                borderRadius: 5, color: 'var(--text-muted)',
              }}>
                ✕
              </button>
            </div>
          </form>
        ) : (
          <button
            onClick={() => onAddStart(col.key)}
            style={{
              width: '100%', background: 'none',
              border: `1px dashed rgba(${col.glow},0.2)`,
              borderRadius: 6, padding: '7px 10px',
              cursor: 'pointer', color: 'var(--text-dim)',
              fontSize: 13, textAlign: 'left',
              transition: 'border-color 0.14s, color 0.14s',
              fontFamily: 'var(--font-sans)',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = `rgba(${col.glow},0.45)`
              e.currentTarget.style.color = col.accent
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = `rgba(${col.glow},0.2)`
              e.currentTarget.style.color = 'var(--text-dim)'
            }}
          >
            + Add task
          </button>
        )}
      </div>
    </div>
  )
}

// ── Main Board component ──────────────────────────────────────────────────────
export function Board() {
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { username } = useAuth()
  const { theme } = useTheme()

  const [selectedTask, setSelectedTask]   = useState<Task | null>(null)
  const [selectedExp,  setSelectedExp]    = useState<Experiment | null>(null)
  const [newTaskTitle, setNewTaskTitle]   = useState('')
  const [addingToCol,  setAddingToCol]    = useState<Task['status'] | null>(null)
  const [activeTaskId, setActiveTaskId]   = useState<string | null>(null)
  const [overColumnId, setOverColumnId]   = useState<string | null>(null)
  const [editingTask,  setEditingTask]    = useState<Task | null>(null)
  const [editAnchorRect, setEditAnchorRect] = useState<DOMRect | null>(null)
  const [settingsPanelOpen, setSettingsPanelOpen] = useState(false)

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

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const taskId  = String(event.active.id)
    const colKey  = event.over ? String(event.over.id) : null
    if (colKey && COLUMNS.some(c => c.key === colKey)) {
      const task = tasks.find(t => String(t.id) === taskId)
      if (task && task.status !== colKey) {
        patchStatus.mutate({ taskId, status: colKey as Task['status'] })
      }
    }
    setActiveTaskId(null)
    setOverColumnId(null)
  }, [tasks, patchStatus])

  const handleAddSubmit = useCallback((colKey: Task['status']) => (title: string) => {
    createTask.mutate({ title, status: colKey })
  }, [createTask])

  const handleAddCancel = useCallback(() => setAddingToCol(null), [])

  const handleCardClick = useCallback((task: Task) => setSelectedTask(task), [])
  const handleExpClick  = useCallback((exp: Experiment) => setSelectedExp(exp), [])

  const handleEditClick = useCallback((task: Task, rect: DOMRect) => {
    setEditingTask(task)
    setEditAnchorRect(rect)
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
            padding: '3px 9px', fontSize: 15, lineHeight: 1,
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
            margin: 0, fontSize: 14, fontWeight: 600,
            letterSpacing: '0.03em', color: 'var(--text-heading)',
            fontFamily: 'var(--font-mono)',
          }}>
            {project?.name ?? '…'} — Kanban Board
          </h1>
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            onClick={() => navigate(`/projects/${projectId}/experiments`)}
            style={{
              background: 'rgba(16,185,129,0.08)',
              border: '1px solid rgba(16,185,129,0.18)',
              color: '#64748b',
              fontFamily: 'var(--font-mono)',
              fontSize: 13,
              padding: '4px 10px',
              borderRadius: 4,
              cursor: 'pointer',
              letterSpacing: '0.08em',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = '#10b981'; e.currentTarget.style.borderColor = 'rgba(16,185,129,0.35)' }}
            onMouseLeave={e => { e.currentTarget.style.color = '#64748b'; e.currentTarget.style.borderColor = 'rgba(16,185,129,0.18)' }}
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
              fontSize: 13,
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
          {isOwner && (
            <button
              onClick={() => setSettingsPanelOpen(true)}
              style={{
                background: 'var(--surface-input)',
                border: '1px solid var(--border)',
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
                fontSize: 13,
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
                  justifyContent: 'center', fontSize: 11, fontWeight: 700,
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
              fontSize: 11, fontWeight: 700, cursor: 'pointer',
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

      {/* ── Columns ── */}
      <DndContext
        sensors={sensors}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
        <div style={{
          display: 'flex', flex: 1, overflowX: 'auto',
          padding: '20px 20px', gap: 16,
          alignItems: 'flex-start',
        }}>
          {COLUMNS.map(col => {
            const colTasks = filtered.filter(t => t.status === col.key)
            const colExps  = experiments.filter(e => EXP_STATUS_TO_COL[e.status] === col.key)
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
                onEditClick={handleEditClick}
                onExpClick={handleExpClick}
                members={project?.members ?? []}
              />
            )
          })}
        </div>
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
        />
      )}

      {editingTask && editAnchorRect && (
        <CardEditPopover
          task={editingTask}
          projectId={projectId!}
          anchorRect={editAnchorRect}
          onClose={() => setEditingTask(null)}
        />
      )}

      {settingsPanelOpen && project && (
        <ProjectSettingsPanel
          project={project}
          projectId={projectId!}
          onClose={() => setSettingsPanelOpen(false)}
        />
      )}
    </div>
  )
}
