import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api, AiJob } from '../api'

function ago(iso: string): string {
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000))
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)} min`
  return `${Math.floor(s / 3600)} h`
}

/**
 * The signed-in user's recent AI jobs for a project or paper: running, done
 * (with a link to the result) or failed (with the reason). Polls only while
 * something is still running.
 */
export function AiJobList({ projectId, publicationId, title = 'Recent AI jobs', onFinished }: {
  projectId?: string; publicationId?: string; title?: string
  /** Called when a job this list saw running has finished, e.g. to refresh the page's data. */
  onFinished?: () => void
}) {
  const navigate = useNavigate()
  const { data: jobs = [] } = useQuery({
    queryKey: ['ai-jobs', projectId ?? null, publicationId ?? null],
    queryFn: () => api.listAiJobs({ projectId, publicationId }),
    refetchInterval: q => ((q.state.data as AiJob[] | undefined)?.some(j => j.status === 'running') ? 3000 : false),
  })
  const running = useRef<Set<string>>(new Set())
  useEffect(() => {
    const now = new Set(jobs.filter(j => j.status === 'running').map(j => j.id))
    const finished = [...running.current].some(id => !now.has(id))
    running.current = now
    if (finished) onFinished?.()
  }, [jobs, onFinished])

  if (jobs.length === 0) return null

  return (
    <section className="job-list" aria-label={title}>
      <h3>{title}</h3>
      {jobs.slice(0, 8).map(j => (
        <div key={j.id} className="job" data-state={j.status}>
          <span className="tool-dot" aria-hidden />
          <div className="job-main">
            <div className="job-title">{j.title}</div>
            <div className="job-meta">
              {j.status === 'running' && `Working… started ${ago(j.created_at)} ago`}
              {j.status === 'done' && `Finished ${ago(j.finished_at ?? j.created_at)} ago`}
              {j.status === 'failed' && (j.error ?? 'Failed')}
            </div>
          </div>
          {j.status === 'done' && j.result_path && (
            <a href={j.result_path} onClick={e => { e.preventDefault(); navigate(j.result_path!) }}>Open →</a>
          )}
        </div>
      ))}
    </section>
  )
}
