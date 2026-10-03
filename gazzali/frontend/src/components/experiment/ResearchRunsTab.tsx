import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ResearchRun } from '../../api'
import { ResearchGateCard } from './ResearchGateCard'
import { RunTimeline } from './RunTimeline'
import { StartRunWizard } from './StartRunWizard'
import { STAGES, stageTitle } from './stageCatalog'

const STATUS_TEXT: Record<ResearchRun['status'], string> = {
  queued: 'Queued', running: 'Running', waiting: 'Needs a decision', done: 'Finished', failed: 'Failed', cancelled: 'Cancelled',
}

function RunRow({ run }: { run: ResearchRun }) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(run.status === 'running' || run.status === 'waiting')
  const cancel = useMutation({
    mutationFn: () => api.cancelResearchRun(run.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['research-runs', run.experiment_id] }),
  })
  const navigate = useNavigate()
  const publish = useMutation({
    mutationFn: () => api.publicationFromRun(run.id),
    onSuccess: r => navigate(`/publications/${r.publication_id}`),
  })
  const active = run.status === 'queued' || run.status === 'running' || run.status === 'waiting'
  return (
    <div style={{ borderTop: '1px solid var(--border)', padding: '10px 0' }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <span className="chip">{STATUS_TEXT[run.status]}{run.status === 'queued' && run.queue_position ? ` · position ${run.queue_position}` : ''}</span>
        <span>{run.stage ? `${run.stage}/23 · ${stageTitle(run.stage)}` : ''}</span>
        {run.stage && STAGES[run.stage] && <span className="chip">{STAGES[run.stage].phase}</span>}
        <span style={{ color: 'var(--text-3)', fontSize: 13 }}>{run.mode} · {new Date(run.created_at).toLocaleString()}</span>
        <button className="btn" style={{ marginLeft: 'auto' }} onClick={() => setOpen(o => !o)} aria-expanded={open}>
          {open ? 'Hide progress' : 'Show progress'}
        </button>
        {active && <button className="btn" disabled={cancel.isPending} onClick={() => cancel.mutate()}>Cancel</button>}
        {run.status === 'done' && (run.publication_id
          ? <a className="btn" href={`/publications/${run.publication_id}`}>Open the paper</a>
          : <button className="btn btn-primary" disabled={publish.isPending} onClick={() => publish.mutate()}>
              {publish.isPending ? 'Creating…' : 'Create publication from this run'}
            </button>)}
      </div>
      <div style={{ fontSize: 14, marginTop: 4 }}>{run.topic}</div>
      {run.error && <div className="msg msg-error" role="alert" style={{ marginTop: 6 }}>{run.error}</div>}
      {cancel.isError && <div className="msg msg-error" role="alert">{(cancel.error as Error).message}</div>}
      {publish.isError && <div className="msg msg-error" role="alert">{(publish.error as Error).message}</div>}
      {open && <div style={{ marginTop: 8 }}><RunTimeline run={run} /></div>}
      {run.status === 'waiting' && <div style={{ marginTop: 8 }}><ResearchGateCard run={run} /></div>}
    </div>
  )
}

/** Finished runs side by side on their primary metric (verified numbers only). */
function CompareRuns({ runs }: { runs: ResearchRun[] }) {
  const done = runs.filter(r => r.primary_metric != null)
  if (done.length < 2) return null
  const maximize = (done[0].metric_direction ?? 'maximize') !== 'minimize'
  const best = done.reduce((a, b) => ((maximize ? b.primary_metric! > a.primary_metric! : b.primary_metric! < a.primary_metric!) ? b : a))
  return (
    <section aria-label="Compare runs" style={{ marginTop: 16 }}>
      <h4 style={{ margin: '0 0 6px' }}>Compare finished runs</h4>
      <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
        <thead><tr><th align="left">Run</th><th align="left">Question</th><th align="right">Primary metric</th><th align="left">Conditions</th></tr></thead>
        <tbody>
          {done.map(r => (
            <tr key={r.id} style={{ fontWeight: r.id === best.id ? 700 : 400 }}>
              <td>{new Date(r.created_at).toLocaleDateString()}</td>
              <td>{r.topic.slice(0, 80)}</td>
              <td align="right">{r.primary_metric!.toFixed(4)}{r.primary_metric_std != null ? ` ± ${r.primary_metric_std.toFixed(4)}` : ''}{r.id === best.id ? ' ★' : ''}</td>
              <td>{(r.conditions ?? []).join(', ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

/**
 * Computational experiments run through AutoResearchClaw (plan/research-pipeline-ux.md).
 * Verified numbers land in Metrics when a run finishes; lessons go to the lab's memory.
 */
export function ResearchRunsTab({ projectId, experimentId, hypothesis }: { projectId: string; experimentId: string; hypothesis?: string | null }) {
  const { data: runs = [] } = useQuery({
    queryKey: ['research-runs', experimentId],
    queryFn: () => api.listResearchRuns(projectId, experimentId),
    refetchInterval: 15_000,
  })
  return (
    <div style={{ padding: '12px 0' }}>
      <StartRunWizard projectId={projectId} experimentId={experimentId} hypothesis={hypothesis} />
      <div style={{ marginTop: 16 }}>
        {runs.length === 0 ? <p style={{ color: 'var(--text-3)' }}>No runs yet.</p> : runs.map(r => <RunRow key={r.id} run={r} />)}
      </div>
      <CompareRuns runs={runs} />
    </div>
  )
}
