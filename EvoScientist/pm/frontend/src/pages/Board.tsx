import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Task } from '../api'
import { TaskDetail } from './TaskDetail'

const COLUMNS: { key: Task['status']; label: string }[] = [
  { key: 'todo', label: 'Todo' },
  { key: 'in_progress', label: 'In Progress' },
  { key: 'done', label: 'Done' },
]

const PRIORITY_DOT: Record<string, string> = { high: '#ef4444', medium: '#f97316', low: '#22c55e' }

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
    mutationFn: (title: string) => api.createTask(projectId!, { title, status: addingToCol ?? 'todo' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      setNewTaskTitle('')
      setAddingToCol(null)
    },
  })

  return (
    <div style={{ fontFamily: 'system-ui', height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '12px 24px', borderBottom: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', gap: 16 }}>
        <button onClick={() => navigate('/projects')} style={{ cursor: 'pointer', background: 'none', border: 'none', fontSize: 20 }}>\u2190</button>
        <h1 style={{ margin: 0, fontSize: 20 }}>{project?.name ?? '\u2026'}</h1>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          {project?.members.map(m => (
            <span key={m.user_id} title={`${m.username} (${m.role})`}
              style={{ width: 32, height: 32, borderRadius: '50%', background: '#6366f1', color: '#fff',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, cursor: 'default' }}>
              {m.username[0].toUpperCase()}
            </span>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', flex: 1, overflowX: 'auto', padding: 24, gap: 16 }}>
        {COLUMNS.map(col => {
          const colTasks = tasks.filter(t => t.status === col.key)
          return (
            <div key={col.key} style={{ flex: '0 0 300px', background: '#f3f4f6', borderRadius: 10, padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <strong>{col.label}</strong>
                <span style={{ fontSize: 13, color: '#666' }}>{colTasks.length}</span>
              </div>

              {colTasks.map(task => (
                <div key={task.id} onClick={() => setSelectedTask(task)}
                  style={{ background: '#fff', borderRadius: 8, padding: 12, cursor: 'pointer', boxShadow: '0 1px 3px rgba(0,0,0,.1)' }}>
                  <p style={{ margin: 0, fontWeight: 500 }}>{task.title}</p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: PRIORITY_DOT[task.priority] }} />
                    <span style={{ fontSize: 12, color: '#666' }}>{task.priority}</span>
                    {task.deadline && <span style={{ fontSize: 12, color: '#999', marginLeft: 'auto' }}>{task.deadline}</span>}
                  </div>
                </div>
              ))}

              {addingToCol === col.key ? (
                <form onSubmit={e => { e.preventDefault(); createTask.mutate(newTaskTitle) }}>
                  <input autoFocus value={newTaskTitle} onChange={e => setNewTaskTitle(e.target.value)}
                    placeholder="Task title" required style={{ width: '100%', padding: 8, boxSizing: 'border-box', marginBottom: 4 }} />
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button type="submit" style={{ flex: 1 }}>Add</button>
                    <button type="button" onClick={() => setAddingToCol(null)}>\u2715</button>
                  </div>
                </form>
              ) : (
                <button onClick={() => setAddingToCol(col.key)}
                  style={{ background: 'none', border: '1px dashed #d1d5db', borderRadius: 6, padding: 8, cursor: 'pointer', color: '#6b7280' }}>
                  + Add task
                </button>
              )}
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
