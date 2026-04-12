import React from 'react'
import { Task, Experiment, ProjectPhase } from '../../api'
import { DroppableColumn } from './DroppableColumn'
import { ColumnDef } from './DraggableCard'

// ── Experiment status → column key ────────────────────────────────────────────
const EXP_STATUS_TO_COL: Record<Experiment['status'], Task['status']> = {
  planned:   'todo',
  running:   'in_progress',
  completed: 'done',
}

// ── Column definitions (must match Board.tsx COLUMNS) ────────────────────────
const COLUMNS: ColumnDef[] = [
  { key: 'todo',        label: 'PLANNED',     accent: '#ff8015', glow: '34,211,238'  },
  { key: 'in_progress', label: 'IN PROGRESS', accent: '#f59e0b', glow: '245,158,11'  },
  { key: 'done',        label: 'COMPLETE',    accent: '#10b981', glow: '16,185,129'  },
]

// ── Props ─────────────────────────────────────────────────────────────────────
export interface PhaseSwimLaneProps {
  phase: ProjectPhase | null  // null = "Unassigned" lane
  tasks: Task[]
  experiments: Experiment[]
  overColumnId: string | null
  activeTaskId: string | null
  addingToCol: Task['status'] | null
  newTaskTitle: string
  onNewTaskTitleChange: (v: string) => void
  onAddStart: (status: Task['status']) => void
  onAddCancel: () => void
  onAddSubmit: (col: Task['status']) => (title: string) => void
  onCardClick: (task: Task) => void
  onEditClick: (task: Task, rect: DOMRect) => void
  onExpClick: (exp: Experiment) => void
  members: { user_id: string; username: string }[]
}

export function PhaseSwimLane({
  phase, tasks, experiments, overColumnId, activeTaskId,
  addingToCol, newTaskTitle, onNewTaskTitleChange,
  onAddStart, onAddCancel, onAddSubmit,
  onCardClick, onEditClick, onExpClick, members,
}: PhaseSwimLaneProps) {
  const totalTasks = tasks.length
  const doneTasks = tasks.filter(t => t.status === 'done').length
  const progressPct = totalTasks > 0 ? Math.round((doneTasks / totalTasks) * 100) : 0

  const phaseColor = phase?.color ?? '#64748b'
  const phaseName = phase?.name ?? 'Unassigned'

  return (
    <div style={{
      display: 'flex',
      borderBottom: '1px solid var(--border-subtle)',
      marginBottom: 0,
      minHeight: 120,
    }}>
      {/* Left label */}
      <div style={{
        width: 120,
        flexShrink: 0,
        borderLeft: `3px solid ${phaseColor}`,
        borderRight: '1px solid var(--border-subtle)',
        padding: '12px 10px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        background: `${phaseColor}08`,
      }}>
        <span style={{
          fontSize: 14,
          fontWeight: 700,
          color: phaseColor,
          fontFamily: 'var(--font-mono)',
          letterSpacing: '0.06em',
          wordBreak: 'break-word',
          lineHeight: 1.3,
        }}>
          {phaseName}
        </span>
        <span style={{
          fontSize: 13,
          color: 'var(--text-dim)',
          fontFamily: 'var(--font-mono)',
        }}>
          {totalTasks} tasks
        </span>
        {totalTasks > 0 && (
          <div style={{ marginTop: 2 }}>
            <div style={{
              height: 4,
              borderRadius: 2,
              background: 'var(--border-subtle)',
              overflow: 'hidden',
            }}>
              <div style={{
                height: '100%',
                width: `${progressPct}%`,
                background: phaseColor,
                borderRadius: 2,
                transition: 'width 0.3s ease',
              }} />
            </div>
            <span style={{
              fontSize: 12,
              color: 'var(--text-dim)',
              fontFamily: 'var(--font-mono)',
              marginTop: 2,
              display: 'block',
            }}>
              {progressPct}%
            </span>
          </div>
        )}
      </div>

      {/* Columns area */}
      <div style={{
        display: 'flex',
        flex: 1,
        gap: 16,
        padding: '12px 16px',
        overflowX: 'auto',
        alignItems: 'flex-start',
      }}>
        {COLUMNS.map(col => {
          const colTasks = tasks.filter(t => t.status === col.key)
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
              onNewTaskTitleChange={onNewTaskTitleChange}
              onAddStart={onAddStart}
              onAddCancel={onAddCancel}
              onAddSubmit={onAddSubmit(col.key)}
              onCardClick={onCardClick}
              onEditClick={onEditClick}
              onExpClick={onExpClick}
              members={members}
            />
          )
        })}
      </div>
    </div>
  )
}
