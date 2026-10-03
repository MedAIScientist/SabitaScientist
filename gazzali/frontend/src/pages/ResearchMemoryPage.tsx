import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { api } from '../api'

/**
 * The lab's research memory (paper §3.6): lessons from past AutoResearchClaw runs,
 * fed into the next runs. Pinned lessons always go first; a PI can pin or remove.
 */
export function ResearchMemoryPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const { data: lessons = [], error } = useQuery({ queryKey: ['research-lessons', id], queryFn: () => api.listResearchLessons(id) })
  const refresh = () => qc.invalidateQueries({ queryKey: ['research-lessons', id] })
  const pin = useMutation({ mutationFn: (l: { id: string; pinned: boolean }) => api.pinResearchLesson(id, l.id, l.pinned), onSuccess: refresh })
  const remove = useMutation({ mutationFn: (lessonId: string) => api.deleteResearchLesson(id, lessonId), onSuccess: refresh })
  const actionError = (pin.error || remove.error) as Error | null

  return (
    <div className="page" style={{ maxWidth: 900, margin: '0 auto', padding: '28px' }}>
      <h1 className="page-title">Research memory</h1>
      <p style={{ color: 'var(--text-3)' }}>
        What AutoResearchClaw learned from this lab’s runs. New runs read these first: pinned lessons, then the most
        recent and severe ones (a lesson’s weight halves every 30 days).
      </p>
      {error && <div className="msg msg-error" role="alert">{(error as Error).message}</div>}
      {actionError && <div className="msg msg-error" role="alert">{actionError.message}</div>}
      {lessons.length === 0 && !error && <p>No lessons yet. They appear after the lab’s first finished run.</p>}
      <ul style={{ listStyle: 'none', padding: 0, display: 'grid', gap: 8 }}>
        {lessons.map(l => (
          <li key={l.id} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 10 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              {l.pinned && <span className="chip">Pinned</span>}
              <span className="chip">{l.category}</span>
              {l.lesson.stage_name && <span style={{ fontSize: 13, color: 'var(--text-3)' }}>{l.lesson.stage_name.replace(/_/g, ' ')}</span>}
              <span style={{ fontSize: 13, color: 'var(--text-3)' }}>weight {l.weight.toFixed(2)} · {new Date(l.created_at).toLocaleDateString()}</span>
              <span style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                <button className="btn" onClick={() => pin.mutate({ id: l.id, pinned: !l.pinned })}>{l.pinned ? 'Unpin' : 'Pin'}</button>
                <button className="btn" onClick={() => window.confirm('Remove this lesson? Future runs will not see it.') && remove.mutate(l.id)}>Remove</button>
              </span>
            </div>
            <div style={{ marginTop: 6 }}>{l.lesson.description ?? JSON.stringify(l.lesson)}</div>
          </li>
        ))}
      </ul>
    </div>
  )
}
