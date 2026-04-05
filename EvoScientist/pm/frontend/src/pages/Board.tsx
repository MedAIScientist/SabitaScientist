import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Task } from '../api'
import { TaskDetail } from './TaskDetail'

const COLUMNS: { key: Task['status']; label: string; accent: string; glow: string; dimBg: string }[] = [
  { key: 'todo',        label: 'Todo',        accent: '#22d3ee', glow: '34,211,238',  dimBg: 'rgba(34,211,238,0.04)'  },
  { key: 'in_progress', label: 'In Progress', accent: '#f59e0b', glow: '245,158,11',  dimBg: 'rgba(245,158,11,0.04)'  },
  { key: 'done',        label: 'Done',        accent: '#10b981', glow: '16,185,129',  dimBg: 'rgba(16,185,129,0.04)'  },
]

const PRIORITY: Record<string, { color: string; label: string }> = {
  high:   { color: '#f43f5e', label: 'HIGH' },
  medium: { color: '#f59e0b', label: 'MED'  },
  low:    { color: '#22c55e', label: 'LOW'  },
}

const AVATAR_COLORS = ['#6366f1', '#ec4899', '#f59e0b', '#22d3ee', '#10b981', '#8b5cf6']

export function Board() {
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [addingToCol, setAddingToCol] = useState<Task['status'] | null>(null)

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.getProject(projectId!),
  })

  const { data: tasks = [] } = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => api.listTasks(projectId!),
    refetchInterval: 15_000,
  })

  const createTask = useMutation({
    mutationFn: (title: string) =>
      api.createTask(projectId!, { title, status: addingToCol ?? 'todo' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      setNewTaskTitle('')
      setAddingToCol(null)
    },
  })

  return (
    <div style={{ background: 'var(--bg)', height: '100vh', display: 'flex', flexDirection: 'column', color: 'var(--text)' }}>

      {/* ── Header ── */}
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
            {project?.name ?? '…'}
          </h1>
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 5 }}>
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

      {/* ── Columns ── */}
      <div style={{
        display: 'flex', flex: 1, overflowX: 'auto',
        padding: '20px 20px', gap: 16,
        alignItems: 'flex-start',
      }}>
        {COLUMNS.map(col => {
          const colTasks = tasks.filter(t => t.status === col.key)
          return (
            <div
              key={col.key}
              style={{
                flex: '0 0 290px',
                background: 'rgba(13,21,38,0.55)',
                border: '1px solid rgba(100,140,200,0.09)',
                borderTop: `2px solid ${col.accent}`,
                borderRadius: '0 0 10px 10px',
                display: 'flex', flexDirection: 'column',
                maxHeight: 'calc(100vh - 112px)',
                overflow: 'hidden',
              }}>

              {/* Column header */}
              <div style={{
                padding: '11px 13px 9px',
                background: col.dimBg,
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
                  {colTasks.length}
                </span>
              </div>

              {/* Cards */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '8px 9px 4px', display: 'flex', flexDirection: 'column', gap: 7 }}>
                {colTasks.map((task, idx) => {
                  const p = PRIORITY[task.priority] ?? PRIORITY.low
                  return (
                    <div
                      key={task.id}
                      onClick={() => setSelectedTask(task)}
                      style={{
                        background: 'rgba(17,30,53,0.75)',
                        border: '1px solid rgba(100,140,200,0.09)',
                        borderRadius: 7, padding: '11px 13px',
                        cursor: 'pointer',
                        transition: 'transform 0.14s, border-color 0.14s, box-shadow 0.14s',
                        animation: 'fadeInUp 0.22s ease both',
                        animationDelay: `${idx * 0.035}s`,
                      }}
                      onMouseEnter={e => {
                        const el = e.currentTarget
                        el.style.transform = 'translateY(-2px)'
                        el.style.borderColor = `rgba(${col.glow},0.3)`
                        el.style.boxShadow = `0 5px 18px rgba(0,0,0,0.28), 0 0 0 1px rgba(${col.glow},0.12)`
                      }}
                      onMouseLeave={e => {
                        const el = e.currentTarget
                        el.style.transform = ''
                        el.style.borderColor = 'rgba(100,140,200,0.09)'
                        el.style.boxShadow = ''
                      }}
                    >
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
                            color: '#3d4e64', fontFamily: 'var(--font-mono)',
                          }}>
                            {task.deadline}
                          </span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Add task footer */}
              <div style={{ padding: '6px 9px 9px', flexShrink: 0 }}>
                {addingToCol === col.key ? (
                  <form onSubmit={e => { e.preventDefault(); createTask.mutate(newTaskTitle) }}>
                    <input
                      autoFocus
                      value={newTaskTitle}
                      onChange={e => setNewTaskTitle(e.target.value)}
                      placeholder="Task title…"
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
                      <button type="button" onClick={() => setAddingToCol(null)} style={{
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
                    onClick={() => setAddingToCol(col.key)}
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
                    + Add task
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {selectedTask && (
        <TaskDetail
          task={selectedTask}
          projectId={projectId!}
          onClose={() => setSelectedTask(null)}
        />
      )}
    </div>
  )
}
