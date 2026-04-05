import React, { useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { DndContext, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import type { DragStartEvent, DragOverEvent, DragEndEvent } from '@dnd-kit/core'
import { useDraggable, useDroppable } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import { api, Task } from '../api'
import { TaskDetail } from './TaskDetail'
import { FilterToolbar } from '../components/FilterToolbar'
import { CardEditPopover } from '../components/CardEditPopover'
import { ProjectSettingsPanel } from '../components/ProjectSettingsPanel'
import { useTaskFilters } from '../hooks/useTaskFilters'
import { useAuth } from '../auth'

// ── Column definitions (lab context) ─────────────────────────────────────────
const COLUMNS: { key: Task['status']; label: string; accent: string; glow: string }[] = [
  { key: 'todo',        label: 'PLANNED',     accent: '#22d3ee', glow: '34,211,238'  },
  { key: 'in_progress', label: 'IN PROGRESS', accent: '#f59e0b', glow: '245,158,11'  },
  { key: 'done',        label: 'COMPLETE',    accent: '#10b981', glow: '16,185,129'  },
]

// ── Priority labels / colors (lab terminology) ────────────────────────────────
const PRIORITY: Record<string, { color: string; label: string }> = {
  high:   { color: '#f43f5e', label: 'CRIT' },
  medium: { color: '#f59e0b', label: 'NORM' },
  low:    { color: '#10b981', label: 'ROUT' },
}

const AVATAR_COLORS = ['#6366f1', '#ec4899', '#f59e0b', '#22d3ee', '#10b981', '#8b5cf6']

// ── Overdue helper ────────────────────────────────────────────────────────────
function isOverdue(task: Task): boolean {
  return Boolean(task.deadline) && new Date(task.deadline!) < new Date()
}

// ── Draggable task card ───────────────────────────────────────────────────────
interface DraggableCardProps {
  task: Task
  col: typeof COLUMNS[number]
  idx: number
  activeTaskId: string | null
  onCardClick: (task: Task) => void
  onEditClick: (task: Task, rect: DOMRect) => void
}

function DraggableCard({ task, col, idx, activeTaskId, onCardClick, onEditClick }: DraggableCardProps) {
  const [isHovered, setIsHovered] = useState(false)
  const { attributes, listeners, setNodeRef, transform } = useDraggable({ id: String(task.id) })

  const p = PRIORITY[task.priority] ?? PRIORITY.low
  const overdue = isOverdue(task)
  const isDragging = activeTaskId === String(task.id)

  const cardStyle: React.CSSProperties = {
    background: 'rgba(17,30,53,0.75)',
    border: '1px solid rgba(100,140,200,0.09)',
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
        el.style.borderColor = overdue ? '#f43f5e' : 'rgba(100,140,200,0.09)'
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
            background: 'rgba(34,211,238,0.1)',
            border: '1px solid rgba(34,211,238,0.22)',
            borderRadius: 4,
            color: '#22d3ee',
            cursor: 'pointer',
            fontSize: 11,
            lineHeight: 1,
            padding: '2px 5px',
            zIndex: 2,
          }}
        >
          ✎
        </button>
      )}

      <p style={{ margin: '0 0 9px', fontWeight: 500, fontSize: 13, lineHeight: 1.4, color: '#dde5f0' }}>
        {task.title}
      </p>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{
          width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
          background: p.color, boxShadow: `0 0 5px ${p.color}88`,
        }} />
        <span style={{
          fontSize: 9, fontWeight: 700, color: p.color,
          letterSpacing: '0.1em', fontFamily: 'var(--font-mono)',
        }}>
          {p.label}
        </span>
        {task.deadline && (
          <span style={{
            marginLeft: 'auto', fontSize: 9,
            color: overdue ? '#f43f5e' : '#3d4e64',
            fontFamily: 'var(--font-mono)',
          }}>
            Due {task.deadline}
          </span>
        )}
      </div>
    </div>
  )
}

// ── Droppable column ──────────────────────────────────────────────────────────
interface DroppableColumnProps {
  col: typeof COLUMNS[number]
  colTasks: Task[]
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
}

function DroppableColumn({
  col, colTasks, isDropTarget, activeTaskId,
  addingToCol, newTaskTitle, onNewTaskTitleChange,
  onAddStart, onAddCancel, onAddSubmit,
  onCardClick, onEditClick,
}: DroppableColumnProps) {
  const { setNodeRef } = useDroppable({ id: col.key })

  const columnStyle: React.CSSProperties = {
    flex: '0 0 290px',
    background: isDropTarget ? `rgba(${col.glow},0.07)` : 'rgba(13,21,38,0.55)',
    border: isDropTarget
      ? `2px solid ${col.accent}`
      : '1px solid rgba(100,140,200,0.09)',
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
        borderBottom: '1px solid rgba(100,140,200,0.07)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        flexShrink: 0,
      }}>
        <span style={{
          fontSize: 10, fontWeight: 700,
          letterSpacing: '0.12em', textTransform: 'uppercase',
          color: col.accent, fontFamily: 'var(--font-mono)',
        }}>
          {col.label}
        </span>
        <span style={{
          fontSize: 10, fontWeight: 700,
          color: col.accent,
          background: `rgba(${col.glow},0.1)`,
          border: `1px solid rgba(${col.glow},0.22)`,
          borderRadius: 9, padding: '1px 7px',
          fontFamily: 'var(--font-mono)',
        }}>
          {col.label} · {colTasks.length}
        </span>
      </div>

      {/* Cards */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 9px 4px', display: 'flex', flexDirection: 'column', gap: 7 }}>
        {colTasks.map((task, idx) => (
          <DraggableCard
            key={task.id}
            task={task}
            col={col}
            idx={idx}
            activeTaskId={activeTaskId}
            onCardClick={onCardClick}
            onEditClick={onEditClick}
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
              placeholder="Experiment title…"
              required
              style={{
                width: '100%', padding: '7px 10px', boxSizing: 'border-box', marginBottom: 5,
                background: 'rgba(7,11,18,0.65)',
                border: `1px solid rgba(${col.glow},0.3)`,
                borderRadius: 6, color: '#e2e8f0', fontSize: 12, outline: 'none',
              }}
            />
            <div style={{ display: 'flex', gap: 4 }}>
              <button type="submit" style={{
                flex: 1, padding: '5px 0', fontSize: 11, cursor: 'pointer',
                background: col.accent, color: '#070b12',
                border: 'none', borderRadius: 5, fontWeight: 700,
                fontFamily: 'var(--font-mono)',
              }}>
                ADD
              </button>
              <button type="button" onClick={onAddCancel} style={{
                padding: '5px 9px', fontSize: 11, cursor: 'pointer',
                background: 'rgba(100,140,200,0.07)',
                border: '1px solid rgba(100,140,200,0.14)',
                borderRadius: 5, color: '#64748b',
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
              cursor: 'pointer', color: '#3d4e64',
              fontSize: 11, textAlign: 'left',
              transition: 'border-color 0.14s, color 0.14s',
              fontFamily: 'var(--font-sans)',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = `rgba(${col.glow},0.45)`
              e.currentTarget.style.color = col.accent
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = `rgba(${col.glow},0.2)`
              e.currentTarget.style.color = '#3d4e64'
            }}
          >
            + Add experiment
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

  const [selectedTask, setSelectedTask]   = useState<Task | null>(null)
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
        background: 'rgba(13,21,38,0.85)',
        backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 10,
        flexShrink: 0,
      }}>
        <button
          onClick={() => navigate('/projects')}
          style={{
            cursor: 'pointer',
            background: 'rgba(100,140,200,0.07)',
            border: '1px solid rgba(100,140,200,0.14)',
            borderRadius: 6, color: '#64748b',
            padding: '3px 9px', fontSize: 15, lineHeight: 1,
            transition: 'color 0.15s, border-color 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.color = '#22d3ee'; e.currentTarget.style.borderColor = 'rgba(34,211,238,0.3)' }}
          onMouseLeave={e => { e.currentTarget.style.color = '#64748b'; e.currentTarget.style.borderColor = 'rgba(100,140,200,0.14)' }}
        >←</button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: '#22d3ee', boxShadow: '0 0 6px #22d3ee',
            flexShrink: 0,
          }} />
          <h1 style={{
            margin: 0, fontSize: 14, fontWeight: 600,
            letterSpacing: '0.03em', color: '#f1f5f9',
            fontFamily: 'var(--font-mono)',
          }}>
            {project?.name ?? '…'} — Kanban Board
          </h1>
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          {isOwner && (
            <button
              onClick={() => setSettingsPanelOpen(true)}
              style={{
                background: 'rgba(100,140,200,0.08)',
                border: '1px solid rgba(100,140,200,0.18)',
                color: '#64748b',
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
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
                  justifyContent: 'center', fontSize: 10, fontWeight: 700,
                  border: '2px solid rgba(7,11,18,0.9)',
                  fontFamily: 'var(--font-mono)',
                  cursor: 'default',
                }}>
                {m.username[0].toUpperCase()}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* ── Header row 2: filter toolbar ── */}
      <div style={{
        padding: '0 24px',
        borderBottom: '1px solid var(--border)',
        background: 'rgba(13,21,38,0.85)',
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
            return (
              <DroppableColumn
                key={col.key}
                col={col}
                colTasks={colTasks}
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
