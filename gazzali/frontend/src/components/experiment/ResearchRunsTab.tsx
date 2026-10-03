import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ResearchMode, ResearchRun } from '../../api'
import { ResearchGateCard, stagePhase } from './ResearchGateCard'

const MODES: { value: ResearchMode; label: string }[] = [
  { value: 'co-pilot', label: 'CoPilot — you decide at the key points (recommended)' },
  { value: 'gate-only', label: 'Gate-only — 3 checkpoints' },
  { value: 'step-by-step', label: 'Step-by-step — approve every stage' },
  { value: 'full-auto', label: 'Full-auto — no human input' },
]

function RunRow({ run }: { run: ResearchRun }) {
  const qc = useQueryClient()
  const cancel = useMutation({
    mutationFn: () => api.cancelResearchRun(run.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['research-runs', run.experiment_id] }),
  })
  const active = run.status === 'running' || run.status === 'waiting'
  return (
    <div style={{ borderTop: '1px solid var(--border)', padding: '10px 0' }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <span className="chip">{run.status}</span>
        <span>{run.stage ? `Stage ${run.stage}/23 · ${stagePhase(run.stage)}` : 'Starting'}</span>
        <span style={{ color: 'var(--text-3)', fontSize: 13 }}>{run.mode} · {new Date(run.created_at).toLocaleString()}</span>
        {run.dataset && <span className="chip">data: {run.dataset}</span>}
        {active && <button className="btn" style={{ marginLeft: 'auto' }} disabled={cancel.isPending} onClick={() => cancel.mutate()}>Cancel</button>}
      </div>
      <div style={{ fontSize: 14, marginTop: 4 }}>{run.topic}</div>
      {run.error && <div className="msg msg-error" role="alert" style={{ marginTop: 6 }}>{run.error}</div>}
      {cancel.isError && <div className="msg msg-error" role="alert">{(cancel.error as Error).message}</div>}
      {run.status === 'waiting' && <div style={{ marginTop: 8 }}><ResearchGateCard run={run} /></div>}
    </div>
  )
}

/**
 * Computational experiments run through AutoResearchClaw (plan/autoresearchclaw-integration.md).
 * Verified numbers land in Metrics when a run finishes; lessons go to the lab's store.
 */
export function ResearchRunsTab({ projectId, experimentId, hypothesis }: { projectId: string; experimentId: string; hypothesis?: string | null }) {
  const qc = useQueryClient()
  const [topic, setTopic] = useState(hypothesis ?? '')
  const [mode, setMode] = useState<ResearchMode>('co-pilot')
  const [dataset, setDataset] = useState('')
  const [irbId, setIrbId] = useState('')
  const { data: runs = [] } = useQuery({
    queryKey: ['research-runs', experimentId],
    queryFn: () => api.listResearchRuns(projectId, experimentId),
    refetchInterval: 15_000,
  })
  const { data: irbs = [] } = useQuery({
    queryKey: ['irbs', projectId, 'approved'],
    queryFn: () => api.listIrbs(projectId, 'approved'),
    enabled: dataset.length > 0,
  })
  const start = useMutation({
    mutationFn: () => api.startResearchRun(projectId, experimentId, {
      topic, mode, ...(dataset ? { dataset, irb_id: irbId } : {}),
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['research-runs', experimentId] }),
  })

  return (
    <div style={{ padding: '12px 0' }}>
      <div style={{ display: 'grid', gap: 8 }}>
        <label className="field">
          <span>Research question</span>
          <textarea className="input" rows={3} value={topic} onChange={e => setTopic(e.target.value)} />
        </label>
        <label className="field">
          <span>Human-in-the-loop</span>
          <select className="input" value={mode} onChange={e => setMode(e.target.value as ResearchMode)}>
            {MODES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Dataset on the server (optional; patient data needs an approved IRB)</span>
          <input className="input" value={dataset} onChange={e => setDataset(e.target.value)} placeholder="e.g. retina/fundus-2026" />
        </label>
        {dataset && (
          <label className="field">
            <span>IRB approval</span>
            <select className="input" value={irbId} onChange={e => setIrbId(e.target.value)}>
              <option value="">Choose an approved IRB…</option>
              {irbs.map(i => <option key={i.id} value={i.id}>{i.title} ({i.protocol_number}{i.expiry_date ? `, until ${i.expiry_date}` : ''})</option>)}
            </select>
          </label>
        )}
        <div>
          <button className="btn btn-primary" disabled={start.isPending || topic.trim().length < 10 || (!!dataset && !irbId)}
            onClick={() => start.mutate()}>{start.isPending ? 'Starting…' : 'Run with AutoResearchClaw'}</button>
        </div>
        {start.isError && <div className="msg msg-error" role="alert">{(start.error as Error).message}</div>}
      </div>
      <div style={{ marginTop: 16 }}>
        {runs.length === 0 ? <p style={{ color: 'var(--text-3)' }}>No runs yet.</p> : runs.map(r => <RunRow key={r.id} run={r} />)}
      </div>
    </div>
  )
}
