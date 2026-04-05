import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Task } from '../api'

interface Props {
  task: Task
  projectId: string
  onClose: () => void
}

const STATUS: Record<string, { color: string; bg: string; label: string }> = {
  todo:        { color: '#22d3ee', bg: 'rgba(34,211,238,0.08)',  label: 'TODO'        },
  in_progress: { color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', label: 'IN PROGRESS' },
  done:        { color: '#10b981', bg: 'rgba(16,185,129,0.08)', label: 'DONE'         },
}

const PRIORITY: Record<string, { color: string; bg: string; label: string }> = {
  high:   { color: '#f43f5e', bg: 'rgba(244,63,94,0.1)',   label: 'HIGH'   },
  medium: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  label: 'MEDIUM' },
  low:    { color: '#22c55e', bg: 'rgba(34,197,94,0.1)',   label: 'LOW'    },
}

export function TaskDetail({ task, projectId, onClose }: Props) {
  const queryClient = useQueryClient()
  const [commentBody, setCommentBody] = useState('')
  const [copied, setCopied] = useState(false)

  const { data: comments = [] } = useQuery({
    queryKey: ['comments', task.id],
    queryFn: () => api.listComments(projectId, task.id),
  })

  const addComment = useMutation({
    mutationFn: (body: string) => api.addComment(projectId, task.id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comments', task.id] })
      setCommentBody('')
    },
  })

  const status   = STATUS[task.status]   ?? STATUS.todo
  const priority = PRIORITY[task.priority] ?? PRIORITY.low

  function copySessionId() {
    navigator.clipboard.writeText(task.session_id!)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(7,11,18,0.72)',
        backdropFilter: 'blur(5px)',
        display: 'flex', justifyContent: 'flex-end',
        zIndex: 100,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--surface)',
          borderLeft: '1px solid rgba(100,140,200,0.12)',
          width: 476, height: '100%', overflowY: 'auto',
          padding: '28px 28px 32px',
          animation: 'slideInRight 0.2s ease',
          display: 'flex', flexDirection: 'column', gap: 20,
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* ── Title + close ── */}
        <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
          <h2 style={{ flex: 1, margin: 0, fontSize: 16, fontWeight: 600, color: '#f1f5f9', lineHeight: 1.35 }}>
            {task.title}
          </h2>
          <button
            onClick={onClose}
            style={{
              flexShrink: 0, cursor: 'pointer',
              background: 'rgba(100,140,200,0.07)',
              border: '1px solid rgba(100,140,200,0.12)',
              borderRadius: 6, color: '#475569',
              width: 28, height: 28, fontSize: 14, lineHeight: 1,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'color 0.14s, border-color 0.14s',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = '#f43f5e'; e.currentTarget.style.borderColor = 'rgba(244,63,94,0.28)' }}
            onMouseLeave={e => { e.currentTarget.style.color = '#475569';  e.currentTarget.style.borderColor = 'rgba(100,140,200,0.12)' }}
          >✕</button>
        </div>

        {/* ── Badges ── */}
        <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
          <span style={{
            padding: '3px 10px', borderRadius: 4,
            background: status.bg, border: `1px solid ${status.color}28`,
            color: status.color, fontSize: 9, fontWeight: 700,
            letterSpacing: '0.12em', fontFamily: 'var(--font-mono)',
          }}>{status.label}</span>
          <span style={{
            padding: '3px 10px', borderRadius: 4,
            background: priority.bg, border: `1px solid ${priority.color}28`,
            color: priority.color, fontSize: 9, fontWeight: 700,
            letterSpacing: '0.12em', fontFamily: 'var(--font-mono)',
          }}>{priority.label}</span>
          {task.deadline && (
            <span style={{
              padding: '3px 10px', borderRadius: 4,
              background: 'rgba(100,140,200,0.07)',
              border: '1px solid rgba(100,140,200,0.12)',
              color: '#94a3b8', fontSize: 9, fontWeight: 500,
              fontFamily: 'var(--font-mono)',
            }}>⏱ {task.deadline}</span>
          )}
        </div>

        <div style={{ height: 1, background: 'rgba(100,140,200,0.07)', flexShrink: 0 }} />

        {/* ── Description ── */}
        {task.description && (
          <p style={{ margin: 0, color: '#94a3b8', fontSize: 13, lineHeight: 1.65 }}>
            {task.description}
          </p>
        )}

        {/* ── Linked session ── */}
        {task.session_id && (
          <div style={{
            background: 'rgba(34,211,238,0.04)',
            border: '1px solid rgba(34,211,238,0.14)',
            borderRadius: 8, padding: '12px 14px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 9 }}>
              <span style={{
                width: 5, height: 5, borderRadius: '50%',
                background: '#22d3ee', boxShadow: '0 0 5px #22d3ee',
              }} />
              <span style={{
                fontSize: 9, fontWeight: 700, color: '#22d3ee',
                letterSpacing: '0.12em', fontFamily: 'var(--font-mono)',
              }}>LINKED SESSION</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <code style={{
                flex: 1, fontSize: 11, color: '#94a3b8',
                fontFamily: 'var(--font-mono)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {task.session_id}
              </code>
              <button
                onClick={copySessionId}
                style={{
                  flexShrink: 0, padding: '3px 10px', fontSize: 10, cursor: 'pointer',
                  background: copied ? 'rgba(16,185,129,0.12)' : 'rgba(34,211,238,0.08)',
                  border: `1px solid ${copied ? 'rgba(16,185,129,0.28)' : 'rgba(34,211,238,0.22)'}`,
                  borderRadius: 5, color: copied ? '#10b981' : '#22d3ee',
                  fontFamily: 'var(--font-mono)', transition: 'all 0.2s',
                }}
              >{copied ? '✓ Copied' : 'Copy'}</button>
            </div>
            <p style={{
              margin: '7px 0 0', fontSize: 10, color: '#3d4e64',
              fontFamily: 'var(--font-mono)',
            }}>
              EvoSci --resume {task.session_id}
            </p>
          </div>
        )}

        {/* ── Comments ── */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              fontSize: 9, fontWeight: 700, color: '#3d4e64',
              letterSpacing: '0.12em', textTransform: 'uppercase',
              fontFamily: 'var(--font-mono)',
            }}>Comments</span>
            <div style={{ flex: 1, height: 1, background: 'rgba(100,140,200,0.07)' }} />
            <span style={{
              fontSize: 9, color: '#3d4e64',
              background: 'rgba(100,140,200,0.07)',
              border: '1px solid rgba(100,140,200,0.1)',
              borderRadius: 9, padding: '1px 7px',
              fontFamily: 'var(--font-mono)',
            }}>{comments.length}</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            {comments.map(c => (
              <div key={c.id} style={{
                background: 'rgba(17,30,53,0.55)',
                border: '1px solid rgba(100,140,200,0.08)',
                borderRadius: 7, padding: '10px 12px',
                animation: 'fadeInUp 0.18s ease',
              }}>
                <p style={{ margin: '0 0 5px', fontSize: 13, color: '#cbd5e1', lineHeight: 1.55 }}>{c.body}</p>
                <p style={{ margin: 0, fontSize: 9, color: '#3d4e64', fontFamily: 'var(--font-mono)' }}>
                  {c.created_at.slice(0, 10)}
                </p>
              </div>
            ))}
            {comments.length === 0 && (
              <p style={{ color: '#334155', fontSize: 12, fontStyle: 'italic', padding: '4px 0' }}>
                No comments yet.
              </p>
            )}
          </div>

          <form
            onSubmit={e => { e.preventDefault(); addComment.mutate(commentBody) }}
            style={{ display: 'flex', gap: 8, marginTop: 'auto' }}
          >
            <input
              value={commentBody}
              onChange={e => setCommentBody(e.target.value)}
              placeholder="Add a comment…"
              required
              style={{
                flex: 1, padding: '9px 12px',
                background: 'rgba(7,11,18,0.6)',
                border: '1px solid rgba(100,140,200,0.12)',
                borderRadius: 7, color: '#e2e8f0',
                fontSize: 12, outline: 'none',
                transition: 'border-color 0.14s',
              }}
              onFocus={e => { e.currentTarget.style.borderColor = 'rgba(34,211,238,0.3)' }}
              onBlur={e => { e.currentTarget.style.borderColor = 'rgba(100,140,200,0.12)' }}
            />
            <button
              type="submit"
              disabled={addComment.isPending}
              style={{
                padding: '9px 16px', fontSize: 11, cursor: 'pointer',
                background: 'rgba(34,211,238,0.1)',
                border: '1px solid rgba(34,211,238,0.25)',
                borderRadius: 7, color: '#22d3ee', fontWeight: 700,
                letterSpacing: '0.05em', transition: 'background 0.14s',
                fontFamily: 'var(--font-mono)',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(34,211,238,0.2)' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'rgba(34,211,238,0.1)' }}
            >POST</button>
          </form>
        </div>
      </div>
    </div>
  )
}
