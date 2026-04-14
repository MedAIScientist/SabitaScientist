import React, { useState } from 'react'
import { useDraggable } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import { Task } from '../../api'

// ── Column type (mirrored to avoid circular imports) ─────────────────────────
export interface ColumnDef {
  key: Task['status']
  label: string
  accent: string
  glow: string
}

// ── Priority labels / colors ─────────────────────────────────────────────────
const PRIORITY: Record<string, { color: string; label: string }> = {
  high:   { color: '#f43f5e', label: 'CRIT' },
  medium: { color: '#f59e0b', label: 'NORM' },
  low:    { color: '#10b981', label: 'ROUT' },
}

// ── Overdue helper ────────────────────────────────────────────────────────────
export function isOverdue(task: Task): boolean {
  return Boolean(task.deadline) && new Date(task.deadline!) < new Date()
}

// ── Props ─────────────────────────────────────────────────────────────────────
export interface DraggableCardProps {
  task: Task
  col: ColumnDef
  idx: number
  activeTaskId: string | null
  onCardClick: (task: Task) => void
  onEditClick: (task: Task, rect: DOMRect) => void
  members: { user_id: string; username: string }[]
  isSelected: boolean
  onToggleSelect: (taskId: string) => void
}

export function DraggableCard({
  task, col, idx, activeTaskId, onCardClick, onEditClick, members,
  isSelected, onToggleSelect,
}: DraggableCardProps) {
  const [isHovered, setIsHovered] = useState(false)
  const { attributes, listeners, setNodeRef, transform } = useDraggable({ id: String(task.id) })

  const p = PRIORITY[task.priority] ?? PRIORITY.low
  const overdue = isOverdue(task)
  const isDragging = activeTaskId === String(task.id)

  const assignee = task.assignee_id ? members.find(m => m.user_id === task.assignee_id) : null
  const descSnippet = task.description
    ? task.description.slice(0, 60) + (task.description.length > 60 ? '…' : '')
    : null

  const cardStyle: React.CSSProperties = {
    background: 'var(--surface-card)',
    border: isSelected ? '1px solid rgba(255,128,21,0.45)' : '1px solid var(--border-subtle)',
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
        el.style.transform = CSS.Transform.toString(transform)
          ? CSS.Transform.toString(transform)!
          : 'translateY(-2px)'
        if (!isSelected) {
          el.style.borderColor = overdue ? '#f43f5e' : `rgba(${col.glow},0.3)`
        }
        el.style.boxShadow = `0 5px 18px rgba(0,0,0,0.28), 0 0 0 1px rgba(${col.glow},0.12)`
      }}
      onMouseLeave={e => {
        setIsHovered(false)
        const el = e.currentTarget
        el.style.transform = CSS.Transform.toString(transform) ?? ''
        el.style.borderColor = isSelected ? 'rgba(255,128,21,0.45)' : (overdue ? '#f43f5e' : 'var(--border-subtle)')
        el.style.boxShadow = ''
      }}
    >
      {/* Selection checkbox (shown when hovered or selected) */}
      {(isHovered || isSelected) && (
        <input
          type="checkbox"
          checked={isSelected}
          readOnly
          onPointerDown={e => e.stopPropagation()}
          onClick={e => {
            e.stopPropagation()
            onToggleSelect(task.id)
          }}
          style={{
            position: 'absolute',
            top: 8,
            left: 8,
            accentColor: '#ff8015',
            zIndex: 2,
          }}
        />
      )}

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
            fontSize: 20,
            lineHeight: 1,
            padding: '2px 5px',
            zIndex: 2,
          }}
        >
          ✎
        </button>
      )}

      <p style={{ margin: '0 0 6px', fontWeight: 500, fontSize: 22, lineHeight: 1.4, color: 'var(--text-heading)' }}>
        {task.title}
      </p>

      {descSnippet && (
        <p style={{ margin: '0 0 8px', fontSize: 20, color: 'var(--text-dim)', lineHeight: 1.4 }}>
          {descSnippet}
        </p>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{
          width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
          background: p.color, boxShadow: `0 0 5px ${p.color}88`,
        }} />
        <span style={{
          fontSize: 15, fontWeight: 700, color: p.color,
          letterSpacing: '0.1em', fontFamily: 'var(--font-mono)',
        }}>
          {p.label}
        </span>
        {task.blocked_by && task.blocked_by.length > 0 && (
          <span style={{
            fontSize: 13, fontWeight: 700, color: '#f43f5e',
            background: 'rgba(244,63,94,0.1)',
            border: '1px solid rgba(244,63,94,0.3)',
            borderRadius: 3, padding: '1px 4px',
            fontFamily: 'var(--font-mono)',
            letterSpacing: '0.08em',
            flexShrink: 0,
          }}>
            BLOCKED
          </span>
        )}
        {assignee && (
          <span
            title={assignee.username}
            style={{
              width: 18, height: 18, borderRadius: '50%',
              background: 'rgba(255,128,21,0.18)',
              border: '1px solid rgba(255,128,21,0.3)',
              color: '#ff8015', fontSize: 15, fontWeight: 700,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--font-mono)', flexShrink: 0,
            }}
          >
            {assignee.username[0].toUpperCase()}
          </span>
        )}
        {task.deadline && (
          <span style={{
            marginLeft: 'auto', fontSize: 15,
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
