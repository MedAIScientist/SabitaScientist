import React, { useState } from 'react'
import { useDroppable } from '@dnd-kit/core'
import { Task, Experiment } from '../../api'
import { DraggableCard, ColumnDef } from './DraggableCard'

// ── Experiment card (non-draggable) ──────────────────────────────────────────
const EXP_ACCENT = '#10b981'
const EXP_GLOW   = '16,185,129'

interface ExperimentCardProps {
  exp: Experiment
  idx: number
  onExpClick: (exp: Experiment) => void
}

function ExperimentCard({ exp, idx, onExpClick }: ExperimentCardProps) {
  const [hovered, setHovered] = useState(false)
  const hypoSnippet = exp.hypothesis
    ? exp.hypothesis.slice(0, 70) + (exp.hypothesis.length > 70 ? '…' : '')
    : null

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
        boxShadow: hovered
          ? `0 5px 18px rgba(0,0,0,0.22), 0 0 0 1px rgba(${EXP_GLOW},0.1)`
          : undefined,
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 6 }}>
        <span style={{
          fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)',
          letterSpacing: '0.08em', color: EXP_ACCENT,
          background: `rgba(${EXP_GLOW},0.1)`,
          border: `1px solid rgba(${EXP_GLOW},0.25)`,
          borderRadius: 3, padding: '1px 5px',
        }}>
          ⚗ EXP
        </span>
        {exp.tags.slice(0, 2).map(tag => (
          <span key={tag} style={{
            fontSize: 18, fontFamily: 'var(--font-mono)',
            color: 'var(--text-dim)',
            background: 'var(--surface-2)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 3, padding: '1px 4px',
          }}>{tag}</span>
        ))}
      </div>

      <p style={{ margin: '0 0 5px', fontWeight: 500, fontSize: 21, lineHeight: 1.4, color: 'var(--text-heading)' }}>
        {exp.name}
      </p>

      {hypoSnippet && (
        <p style={{ margin: '0 0 6px', fontSize: 16, color: 'var(--text-dim)', lineHeight: 1.4, fontStyle: 'italic' }}>
          {hypoSnippet}
        </p>
      )}

      {exp.deadline && (
        <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
          Due {exp.deadline}
        </div>
      )}
    </div>
  )
}

// ── Props ─────────────────────────────────────────────────────────────────────
export interface DroppableColumnProps {
  col: ColumnDef
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
  selectedIds: Set<string>
  onToggleSelect: (taskId: string) => void
}

export function DroppableColumn({
  col, colTasks, colExps, isDropTarget, activeTaskId,
  addingToCol, newTaskTitle, onNewTaskTitleChange,
  onAddStart, onAddCancel, onAddSubmit,
  onCardClick, onEditClick, onExpClick, members,
  selectedIds, onToggleSelect,
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
          fontSize: 16, fontWeight: 700,
          letterSpacing: '0.12em', textTransform: 'uppercase',
          color: col.accent, fontFamily: 'var(--font-mono)',
        }}>
          {col.label}
        </span>
        <span style={{
          fontSize: 16, fontWeight: 700,
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
            isSelected={selectedIds.has(task.id)}
            onToggleSelect={onToggleSelect}
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

      {/* Add task footer */}
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
                borderRadius: 6, color: 'var(--text)', fontSize: 21, outline: 'none',
              }}
            />
            <div style={{ display: 'flex', gap: 4 }}>
              <button type="submit" style={{
                flex: 1, padding: '5px 0', fontSize: 20, cursor: 'pointer',
                background: col.accent, color: '#070b12',
                border: 'none', borderRadius: 5, fontWeight: 700,
                fontFamily: 'var(--font-mono)',
              }}>
                ADD
              </button>
              <button type="button" onClick={onAddCancel} style={{
                padding: '5px 9px', fontSize: 20, cursor: 'pointer',
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
              fontSize: 20, textAlign: 'left',
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
