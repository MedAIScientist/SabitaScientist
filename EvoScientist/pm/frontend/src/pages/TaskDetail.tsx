import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Task } from '../api'

interface Props {
  task: Task
  projectId: string
  onClose: () => void
}

export function TaskDetail({ task, projectId, onClose }: Props) {
  const queryClient = useQueryClient()
  const [commentBody, setCommentBody] = useState('')

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

  const priorityColors: Record<string, string> = { high: '#ef4444', medium: '#f97316', low: '#22c55e' }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', justifyContent: 'flex-end' }} onClick={onClose}>
      <div style={{ background: '#fff', width: 480, height: '100%', overflowY: 'auto', padding: 24 }} onClick={e => e.stopPropagation()}>
        <button onClick={onClose} style={{ float: 'right', cursor: 'pointer', background: 'none', border: 'none', fontSize: 18 }}>\u2715</button>
        <h2 style={{ margin: '0 0 8px' }}>{task.title}</h2>

        <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
          <span style={{ padding: '2px 8px', borderRadius: 4, background: '#f3f4f6', fontSize: 13 }}>{task.status}</span>
          <span style={{ padding: '2px 8px', borderRadius: 4, background: priorityColors[task.priority], color: '#fff', fontSize: 13 }}>
            {task.priority}
          </span>
          {task.deadline && <span style={{ fontSize: 13, color: '#666' }}>Due {task.deadline}</span>}
        </div>

        {task.description && <p style={{ color: '#444', marginBottom: 16 }}>{task.description}</p>}

        {task.session_id && (
          <div style={{ background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 6, padding: 10, marginBottom: 16 }}>
            <strong style={{ fontSize: 13 }}>Linked Session</strong>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              <code style={{ fontSize: 12, flex: 1 }}>{task.session_id}</code>
              <button onClick={() => navigator.clipboard.writeText(task.session_id!)} style={{ fontSize: 12, cursor: 'pointer' }}>
                Copy
              </button>
            </div>
            <p style={{ fontSize: 12, color: '#666', margin: '4px 0 0' }}>
              Resume in CLI: <code>EvoSci --resume {task.session_id}</code>
            </p>
          </div>
        )}

        <h3 style={{ marginBottom: 8 }}>Comments</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
          {comments.map(c => (
            <div key={c.id} style={{ background: '#f9fafb', borderRadius: 6, padding: 10 }}>
              <p style={{ margin: 0, fontSize: 14 }}>{c.body}</p>
              <p style={{ margin: '4px 0 0', fontSize: 12, color: '#999' }}>{c.created_at.slice(0, 10)}</p>
            </div>
          ))}
          {comments.length === 0 && <p style={{ color: '#999', fontSize: 14 }}>No comments yet.</p>}
        </div>

        <form onSubmit={e => { e.preventDefault(); addComment.mutate(commentBody) }} style={{ display: 'flex', gap: 8 }}>
          <input
            value={commentBody} onChange={e => setCommentBody(e.target.value)}
            placeholder="Add a comment\u2026" style={{ flex: 1, padding: 8 }} required
          />
          <button type="submit" disabled={addComment.isPending}>Post</button>
        </form>
      </div>
    </div>
  )
}
