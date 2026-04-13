// EvoScientist/pm/frontend/src/components/task/TaskDetailView.tsx
import React from 'react'
import { DependencyPicker } from '../DependencyPicker'
import { STATUS_META, PRIORITY_META, isOverdue, labelStyle } from './taskStyles'
import type { Task, Member } from '../../api'

interface Props {
  task: Task & { blocked_by?: string[] }
  projectId: string
  members: Member[]
  token: string | null
  allTasks: { id: string; title: string }[]
  copied: boolean
  onCopySessionId: () => void
}

export function TaskDetailView({ task, projectId, members, token, allTasks, copied, onCopySessionId }: Props) {
  const status   = STATUS_META[task.status]   ?? STATUS_META.todo
  const priority = PRIORITY_META[task.priority] ?? PRIORITY_META.low
  const overdue  = isOverdue(task.deadline)

  const deadlineBadgeStyle: React.CSSProperties = overdue
    ? {
        padding: '3px 10px', borderRadius: 4,
        background: 'rgba(244,63,94,0.12)',
        border: '1px solid rgba(244,63,94,0.28)',
        color: '#f43f5e', fontSize: 15, fontWeight: 700,
        fontFamily: 'var(--font-mono)',
      }
    : {
        padding: '3px 10px', borderRadius: 4,
        background: 'var(--border-subtle)',
        border: '1px solid var(--border)',
        color: '#94a3b8', fontSize: 15, fontWeight: 500,
        fontFamily: 'var(--font-mono)',
      }

  return (
    <>
      {/* Badges */}
      <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
        <span style={{
          padding: '3px 10px', borderRadius: 4,
          background: status.bg, border: `1px solid ${status.color}28`,
          color: status.color, fontSize: 15, fontWeight: 700,
          letterSpacing: '0.12em', fontFamily: 'var(--font-mono)',
        }}>{status.label}</span>
        <span style={{
          padding: '3px 10px', borderRadius: 4,
          background: priority.bg, border: `1px solid ${priority.color}28`,
          color: priority.color, fontSize: 15, fontWeight: 700,
          letterSpacing: '0.12em', fontFamily: 'var(--font-mono)',
        }}>{priority.label}</span>
        {task.deadline && (
          <span style={deadlineBadgeStyle}>⏱ {task.deadline}</span>
        )}
        {task.blocked_by && task.blocked_by.length > 0 && (
          <span style={{
            padding: '3px 10px', borderRadius: 4,
            background: 'rgba(244,63,94,0.1)',
            border: '1px solid rgba(244,63,94,0.28)',
            color: '#f43f5e', fontSize: 15, fontWeight: 700,
            letterSpacing: '0.08em', fontFamily: 'var(--font-mono)',
          }}>BLOCKED</span>
        )}
      </div>

      <div style={{ height: 1, background: 'var(--border-subtle)', flexShrink: 0 }} />

      {/* Description */}
      {task.description && (
        <p style={{ margin: 0, color: 'var(--text-2)', fontSize: 22, lineHeight: 1.65 }}>
          {task.description}
        </p>
      )}

      {/* Assigned researcher */}
      {task.assignee_id && (
        <div>
          <span style={labelStyle}>Assigned Researcher</span>
          <span style={{ color: 'var(--text-2)', fontSize: 18 }}>
            {members.find(m => m.user_id === task.assignee_id)?.username ?? task.assignee_id}
          </span>
        </div>
      )}

      {/* Linked session */}
      {task.session_id && (
        <div style={{
          background: 'rgba(255,128,21,0.04)',
          border: '1px solid rgba(255,128,21,0.14)',
          borderRadius: 8, padding: '12px 14px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 9 }}>
            <span style={{
              width: 5, height: 5, borderRadius: '50%',
              background: '#ff8015', boxShadow: '0 0 5px #ff8015',
            }} />
            <span style={{
              fontSize: 15, fontWeight: 700, color: '#ff8015',
              letterSpacing: '0.12em', fontFamily: 'var(--font-mono)',
            }}>LINKED SESSION</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <code style={{
              flex: 1, fontSize: 20, color: 'var(--text-2)',
              fontFamily: 'var(--font-mono)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {task.session_id}
            </code>
            <button
              onClick={onCopySessionId}
              aria-label={copied ? 'Copied' : 'Copy'}
              style={{
                flexShrink: 0, padding: '3px 10px', fontSize: 16, cursor: 'pointer',
                background: copied ? 'rgba(16,185,129,0.12)' : 'rgba(255,128,21,0.08)',
                border: `1px solid ${copied ? 'rgba(16,185,129,0.28)' : 'rgba(255,128,21,0.22)'}`,
                borderRadius: 5, color: copied ? '#10b981' : '#ff8015',
                fontFamily: 'var(--font-mono)', transition: 'all 0.2s',
              }}
            >{copied ? '✓ Copied' : 'Copy'}</button>
          </div>
          <p style={{
            margin: '7px 0 0', fontSize: 16, color: 'var(--text-dim)',
            fontFamily: 'var(--font-mono)',
          }}>
            EvoSci --resume {task.session_id}
          </p>
        </div>
      )}

      {/* Dependencies */}
      {token && (
        <DependencyPicker
          projectId={projectId}
          taskId={task.id}
          token={token}
          allTasks={allTasks}
        />
      )}
    </>
  )
}
