import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Task, Member } from '../api'
import { AiRunsTab } from '../components/AiRunsTab'
import { DeadlinePicker } from '../components/DeadlinePicker'
import { DependencyPicker } from '../components/DependencyPicker'
import { useAuth } from '../auth'

interface Props {
  task: Task
  projectId: string
  onClose: () => void
  members: Member[]
}

const STATUS_META: Record<string, { color: string; bg: string; label: string }> = {
  todo:        { color: '#ff8015', bg: 'rgba(255,128,21,0.08)',  label: 'PLANNED'     },
  in_progress: { color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', label: 'IN PROGRESS' },
  done:        { color: '#10b981', bg: 'rgba(16,185,129,0.08)', label: 'COMPLETE'    },
}

const PRIORITY_META: Record<string, { color: string; bg: string; label: string }> = {
  high:   { color: '#f43f5e', bg: 'rgba(244,63,94,0.1)',   label: 'CRITICAL' },
  medium: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  label: 'STANDARD' },
  low:    { color: '#22c55e', bg: 'rgba(34,197,94,0.1)',   label: 'ROUTINE'  },
}

function isOverdue(deadline: string | null): boolean {
  return Boolean(deadline) && new Date(deadline!) < new Date()
}

// ── Shared input style ────────────────────────────────────────────────────────
const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 11px',
  background: 'var(--surface-input)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  color: 'var(--text)',
  fontSize: 22,
  outline: 'none',
  boxSizing: 'border-box',
  fontFamily: 'inherit',
}

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  cursor: 'pointer',
}

const labelStyle: React.CSSProperties = {
  fontSize: 15,
  fontWeight: 700,
  color: 'var(--text-dim)',
  letterSpacing: '0.12em',
  textTransform: 'uppercase' as const,
  fontFamily: 'var(--font-mono)',
  marginBottom: 5,
  display: 'block',
}

export function TaskDetail({ task, projectId, onClose, members }: Props) {
  const queryClient = useQueryClient()
  const { token } = useAuth()

  // ── All tasks query (for DependencyPicker) ──
  const { data: allTasksData = [] } = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => api.listTasks(projectId),
  })

  const allTasks = allTasksData.map((t: Task) => ({ id: t.id, title: t.title }))

  // ── Comment state ──
  const [commentBody, setCommentBody] = useState('')
  const [copied, setCopied] = useState(false)

  // ── Edit mode state ──
  const [editMode, setEditMode] = useState(false)
  const [editTitle, setEditTitle] = useState(task.title)
  const [editStatus, setEditStatus] = useState<Task['status']>(task.status)
  const [editPriority, setEditPriority] = useState<Task['priority']>(task.priority)
  const [editDeadline, setEditDeadline] = useState(task.deadline ?? '')
  const [editDescription, setEditDescription] = useState(task.description ?? '')
  const [editAssigneeId, setEditAssigneeId] = useState(task.assignee_id ?? '')

  // ── Tab state ──
  const [activeTab, setActiveTab] = useState<'details' | 'ai'>('details')

  // ── Delete confirmation state ──
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const deleteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Comments query ──
  const { data: comments = [] } = useQuery({
    queryKey: ['comments', task.id],
    queryFn: () => api.listComments(projectId, task.id),
  })

  // ── Add comment mutation ──
  const addComment = useMutation({
    mutationFn: (body: string) => api.addComment(projectId, task.id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comments', task.id] })
      setCommentBody('')
    },
  })

  // ── Update task mutation ──
  const updateTask = useMutation({
    mutationFn: (data: Partial<Task>) => api.updateTask(projectId, task.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      setEditMode(false)
    },
  })

  // ── Delete task mutation ──
  const deleteTask = useMutation({
    mutationFn: () => api.deleteTask(projectId, task.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      onClose()
    },
  })

  // Clean up timers on unmount
  useEffect(() => {
    return () => {
      if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current)
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
    }
  }, [])

  const status   = STATUS_META[task.status]   ?? STATUS_META.todo
  const priority = PRIORITY_META[task.priority] ?? PRIORITY_META.low
  const overdue  = isOverdue(task.deadline)

  async function copySessionId() {
    if (!task.session_id) return
    try {
      await navigator.clipboard.writeText(task.session_id)
      setCopied(true)
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
      copyTimerRef.current = setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard unavailable (non-https context) — silent fail is acceptable
    }
  }

  function enterEditMode() {
    setEditTitle(task.title)
    setEditStatus(task.status)
    setEditPriority(task.priority)
    setEditDeadline(task.deadline ?? '')
    setEditDescription(task.description ?? '')
    setEditAssigneeId(task.assignee_id ?? '')
    setDeleteConfirm(false)
    setEditMode(true)
  }

  function cancelEdit() {
    setEditMode(false)
    setDeleteConfirm(false)
    if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current)
  }

  function handleSave() {
    updateTask.mutate({
      title: editTitle,
      status: editStatus,
      priority: editPriority,
      deadline: editDeadline || null,
      description: editDescription || null,
      assignee_id: editAssigneeId || null,
    })
  }

  function handleDeleteClick() {
    if (!deleteConfirm) {
      setDeleteConfirm(true)
      deleteTimerRef.current = setTimeout(() => setDeleteConfirm(false), 3000)
    } else {
      if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current)
      deleteTask.mutate()
    }
  }

  // ── Deadline badge style (view mode) ─────────────────────────────────────────
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
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'var(--overlay-bg)',
        backdropFilter: 'blur(4px)',
        display: 'flex', justifyContent: 'flex-end',
        zIndex: 100,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--surface)',
          borderLeft: '1px solid var(--border)',
          boxShadow: '-6px 0 24px rgba(0,0,0,0.12)',
          width: 476, height: '100%', overflowY: 'auto',
          padding: '28px 28px 32px',
          animation: 'slideInRight 0.2s ease',
          display: 'flex', flexDirection: 'column', gap: 20,
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* ── Title + close + edit ── */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          {editMode ? (
            <h2 style={{ flex: 1, margin: 0, fontSize: 24, fontWeight: 600, color: 'var(--text-heading)', lineHeight: 1.35 }}>
              {/* In edit mode the title is in the edit form below; just show a placeholder here */}
              &nbsp;
            </h2>
          ) : (
            <h2 style={{ flex: 1, margin: 0, fontSize: 24, fontWeight: 600, color: 'var(--text-heading)', lineHeight: 1.35, display: 'flex', alignItems: 'flex-start', gap: 8, flexWrap: 'wrap' }}>
              <span>{task.title}</span>
              {task.blocked_by && task.blocked_by.length > 0 && (
                <span style={{
                  fontSize: 13, fontWeight: 700, padding: '2px 8px',
                  borderRadius: 4,
                  background: 'rgba(244,63,94,0.1)',
                  border: '1px solid rgba(244,63,94,0.28)',
                  color: '#f43f5e',
                  fontFamily: 'var(--font-mono)',
                  letterSpacing: '0.08em',
                  whiteSpace: 'nowrap',
                  alignSelf: 'center',
                }}>BLOCKED</span>
              )}
            </h2>
          )}
          {!editMode && (
            <button
              onClick={enterEditMode}
              style={{
                flexShrink: 0, cursor: 'pointer',
                background: 'rgba(255,128,21,0.08)',
                border: '1px solid rgba(255,128,21,0.22)',
                borderRadius: 6, color: '#ff8015',
                padding: '4px 10px', fontSize: 16, fontWeight: 700,
                letterSpacing: '0.08em',
                fontFamily: 'var(--font-mono)',
                lineHeight: 1,
                transition: 'background 0.14s',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.18)' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.08)' }}
            >EDIT</button>
          )}
          <button
            onClick={onClose}
            style={{
              flexShrink: 0, cursor: 'pointer',
              background: 'var(--border-subtle)',
              border: '1px solid var(--border)',
              borderRadius: 6, color: 'var(--text-3)',
              width: 28, height: 28, fontSize: 21, lineHeight: 1,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'color 0.14s, border-color 0.14s',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = '#f43f5e'; e.currentTarget.style.borderColor = 'rgba(244,63,94,0.28)' }}
            onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-3)';  e.currentTarget.style.borderColor = 'var(--border)' }}
          >✕</button>
        </div>

        {/* ── Tab bar ── */}
        {!editMode && (
          <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', marginBottom: 8 }}>
            <button
              onClick={() => setActiveTab('details')}
              style={{
                padding: '4px 10px', fontSize: 15, fontFamily: 'var(--font-mono)',
                color: activeTab === 'details' ? '#ff8015' : 'var(--text-3)',
                background: 'none', border: 'none', borderBottomStyle: 'solid',
                borderBottomWidth: 2, borderBottomColor: activeTab === 'details' ? '#ff8015' : 'transparent',
                cursor: 'pointer', fontWeight: activeTab === 'details' ? 700 : 400,
              }}
            >
              DETAILS
            </button>
            <button
              onClick={() => setActiveTab('ai')}
              style={{
                padding: '4px 10px', fontSize: 15, fontFamily: 'var(--font-mono)',
                color: activeTab === 'ai' ? '#ff8015' : 'var(--text-3)',
                background: 'none', border: 'none', borderBottomStyle: 'solid',
                borderBottomWidth: 2, borderBottomColor: activeTab === 'ai' ? '#ff8015' : 'transparent',
                cursor: 'pointer', fontWeight: activeTab === 'ai' ? 700 : 400,
              }}
            >
              ⬡ AI RUNS
            </button>
          </div>
        )}

        {/* ── VIEW MODE ─────────────────────────────────────────────────────── */}
        {!editMode && (
          <>
            {activeTab === 'details' ? (
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
                    onClick={copySessionId}
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

            {/* Lab Notes (Comments) */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  fontSize: 15, fontWeight: 700, color: 'var(--text-dim)',
                  letterSpacing: '0.12em', textTransform: 'uppercase',
                  fontFamily: 'var(--font-mono)',
                }}>Lab Notes</span>
                <div style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
                <span style={{
                  fontSize: 15, color: 'var(--text-dim)',
                  background: 'var(--border-subtle)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 9, padding: '1px 7px',
                  fontFamily: 'var(--font-mono)',
                }}>{comments.length}</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                {comments.map((c: { id: string; body: string; created_at: string }) => (
                  <div key={c.id} style={{
                    background: 'var(--surface-comment)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 7, padding: '10px 12px',
                    animation: 'fadeInUp 0.18s ease',
                  }}>
                    <p style={{ margin: '0 0 5px', fontSize: 22, color: 'var(--text)', lineHeight: 1.55 }}>{c.body}</p>
                    <p style={{ margin: 0, fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                      {c.created_at.slice(0, 10)}
                    </p>
                  </div>
                ))}
                {comments.length === 0 && (
                  <p style={{ color: 'var(--text-muted)', fontSize: 21, fontStyle: 'italic', padding: '4px 0' }}>
                    No lab notes yet.
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
                  placeholder="Add a lab note…"
                  required
                  style={{
                    flex: 1, padding: '9px 12px',
                    background: 'var(--surface-input)',
                    border: '1px solid var(--border)',
                    borderRadius: 7, color: 'var(--text)',
                    fontSize: 21, outline: 'none',
                    transition: 'border-color 0.14s',
                  }}
                  onFocus={e => { e.currentTarget.style.borderColor = 'rgba(255,128,21,0.3)' }}
                  onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
                />
                <button
                  type="submit"
                  disabled={addComment.isPending}
                  style={{
                    padding: '9px 16px', fontSize: 20, cursor: 'pointer',
                    background: 'rgba(255,128,21,0.1)',
                    border: '1px solid rgba(255,128,21,0.25)',
                    borderRadius: 7, color: '#ff8015', fontWeight: 700,
                    letterSpacing: '0.05em', transition: 'background 0.14s',
                    fontFamily: 'var(--font-mono)',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.2)' }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.1)' }}
                >POST</button>
              </form>
            </div>
            </> ) : (
              <AiRunsTab task={task} projectId={projectId} />
            )}
          </>
        )}

        {/* ── EDIT MODE ─────────────────────────────────────────────────────── */}
        {editMode && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Experiment Title */}
            <div>
              <label style={labelStyle}>Experiment Title</label>
              <input
                value={editTitle}
                onChange={e => setEditTitle(e.target.value)}
                style={inputStyle}
                onFocus={e => { e.currentTarget.style.borderColor = 'rgba(255,128,21,0.3)' }}
                onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
              />
            </div>

            {/* Protocol Status */}
            <div>
              <label style={labelStyle}>Protocol Status</label>
              <select
                value={editStatus}
                onChange={e => setEditStatus(e.target.value as Task['status'])}
                style={selectStyle}
              >
                <option value="todo">PLANNED</option>
                <option value="in_progress">IN PROGRESS</option>
                <option value="done">COMPLETE</option>
              </select>
            </div>

            {/* Priority Level */}
            <div>
              <label style={labelStyle}>Priority Level</label>
              <select
                value={editPriority}
                onChange={e => setEditPriority(e.target.value as Task['priority'])}
                style={selectStyle}
              >
                <option value="high">CRITICAL</option>
                <option value="medium">STANDARD</option>
                <option value="low">ROUTINE</option>
              </select>
            </div>

            {/* Deadline */}
            <div>
              <label style={labelStyle}>Deadline</label>
              <DeadlinePicker
                value={editDeadline}
                onChange={setEditDeadline}
                inputStyle={inputStyle}
              />
            </div>

            {/* Experiment Notes */}
            <div>
              <label style={labelStyle}>Experiment Notes</label>
              <textarea
                value={editDescription}
                onChange={e => setEditDescription(e.target.value)}
                rows={4}
                style={{
                  ...inputStyle,
                  resize: 'vertical',
                  lineHeight: 1.55,
                }}
                onFocus={e => { e.currentTarget.style.borderColor = 'rgba(255,128,21,0.3)' }}
                onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
              />
            </div>

            {/* Assigned Researcher */}
            <div>
              <label style={labelStyle}>Assigned Researcher</label>
              <select
                value={editAssigneeId}
                onChange={e => setEditAssigneeId(e.target.value)}
                style={selectStyle}
              >
                <option value="">Unassigned</option>
                {members.map(m => (
                  <option key={m.user_id} value={m.user_id}>{m.username}</option>
                ))}
              </select>
            </div>

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
              <button
                onClick={handleSave}
                disabled={updateTask.isPending}
                style={{
                  flex: 1, padding: '9px 0', fontSize: 20, cursor: 'pointer',
                  background: 'rgba(255,128,21,0.1)',
                  border: '1px solid rgba(255,128,21,0.28)',
                  borderRadius: 7, color: '#ff8015', fontWeight: 700,
                  letterSpacing: '0.08em', fontFamily: 'var(--font-mono)',
                  transition: 'background 0.14s',
                  opacity: updateTask.isPending ? 0.6 : 1,
                }}
                onMouseEnter={e => { if (!updateTask.isPending) e.currentTarget.style.background = 'rgba(255,128,21,0.2)' }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.1)' }}
              >{updateTask.isPending ? 'saving…' : 'SAVE'}</button>

              <button
                onClick={cancelEdit}
                style={{
                  padding: '9px 16px', fontSize: 20, cursor: 'pointer',
                  background: 'var(--border-subtle)',
                  border: '1px solid var(--border)',
                  borderRadius: 7, color: '#64748b', fontWeight: 700,
                  letterSpacing: '0.08em', fontFamily: 'var(--font-mono)',
                }}
              >CANCEL</button>
            </div>

            {/* Delete button */}
            <button
              onClick={handleDeleteClick}
              disabled={deleteTask.isPending}
              style={{
                width: '100%', padding: '8px 0', fontSize: 20, cursor: 'pointer',
                background: deleteConfirm ? 'rgba(244,63,94,0.15)' : 'rgba(244,63,94,0.07)',
                border: `1px solid ${deleteConfirm ? 'rgba(244,63,94,0.4)' : 'rgba(244,63,94,0.2)'}`,
                borderRadius: 7, color: '#f43f5e', fontWeight: 700,
                letterSpacing: '0.08em', fontFamily: 'var(--font-mono)',
                transition: 'all 0.18s',
              }}
            >{deleteConfirm ? 'CONFIRM DELETE ?' : 'DELETE'}</button>
          </div>
        )}
      </div>
    </div>
  )
}
