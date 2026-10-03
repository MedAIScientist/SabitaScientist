import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { supervisionApi } from '../../api'

/**
 * A stored AI brief with a "Prepare" button. The brief is an AI job: we poll the job
 * until it ends, then show the new brief, or the reason it could not be written.
 */
function BriefCard({ title, queryKey, load, start, hint }: {
  title: string; queryKey: unknown[]; hint: string
  load: () => Promise<{ content: string; created_at: string } | null>
  start: () => Promise<{ job_id: string }>
}) {
  const qc = useQueryClient()
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { data: brief } = useQuery({ queryKey, queryFn: load })
  useQuery({
    queryKey: ['ai-job', jobId],
    queryFn: async () => {
      const job = await supervisionApi.getAiJob(jobId!)
      if (job.status !== 'running') {
        setJobId(null)
        if (job.status === 'failed') setError(job.error ?? 'The brief could not be prepared.')
        qc.invalidateQueries({ queryKey })
      }
      return job
    },
    enabled: Boolean(jobId),
    refetchInterval: 2000,
  })

  async function prepare() {
    setError(null)
    try { setJobId((await start()).job_id) } catch (e) { setError(e instanceof Error ? e.message : 'Request failed') }
  }

  return (
    <section className="request" aria-label={title}>
      <div className="request-head" style={{ marginBottom: 8 }}>
        <div>
          <div className="request-title">{title}</div>
          <div className="request-meta">
            {brief ? `Prepared ${new Date(brief.created_at).toLocaleString()}` : hint}
          </div>
        </div>
        <button className="btn btn-primary" onClick={prepare} disabled={Boolean(jobId)}>
          {jobId ? 'Preparing…' : brief ? 'Prepare again' : 'Prepare'}
        </button>
      </div>
      {error && <div className="msg msg-error" role="alert">{error}</div>}
      {brief && <div className="brief">{brief.content}</div>}
      <p className="hint" style={{ marginTop: 8 }}>Written by AI from recorded weekly updates, follow-ups and attendance only. Check before relying on it.</p>
    </section>
  )
}

export function StudentMeetingBrief({ studentId }: { studentId: string }) {
  return (
    <BriefCard title="Meeting brief" queryKey={['meeting-brief', studentId]}
      hint="What changed, what is stuck, and three questions to ask."
      load={() => supervisionApi.latestMeetingBrief(studentId)}
      start={() => supervisionApi.startMeetingBrief(studentId)} />
  )
}

export function GroupAgenda() {
  return (
    <BriefCard title="Group meeting agenda" queryKey={['group-agenda']}
      hint="Highlights, what needs discussion, and a suggested order — from this week's updates."
      load={() => supervisionApi.latestGroupAgenda()}
      start={() => supervisionApi.startGroupAgenda()} />
  )
}
