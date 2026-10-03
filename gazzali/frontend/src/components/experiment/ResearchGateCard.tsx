import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, GateAction, ResearchRun } from '../../api'

// Paper §3.1: Discovery 1–9, Experimentation 10–15, Writing 16–23.
export function stagePhase(stage: number | null): string {
  if (stage == null) return 'Starting'
  return stage <= 9 ? 'Discovery' : stage <= 15 ? 'Experiment' : 'Writing'
}

/** From result analysis on, a PI of the lab decides (plan §4.1). */
export const isPostExperiment = (stage: number | null) => stage != null && stage >= 14

/** One AutoResearchClaw gate waiting for a human: what it produced, and the decision. */
export function ResearchGateCard({ run }: { run: ResearchRun }) {
  const qc = useQueryClient()
  const [guidance, setGuidance] = useState('')
  const [file, setFile] = useState<{ path: string; content: string } | null>(null)
  const w = run.waiting
  const decide = useMutation({
    mutationFn: (action: GateAction) => api.respondResearchGate(run.id, { action, guidance, message: guidance }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['research-gates'] })
      qc.invalidateQueries({ queryKey: ['research-runs', run.experiment_id] })
    },
  })
  const open = useMutation({
    mutationFn: (path: string) => api.researchRunFile(run.id, path),
    onSuccess: setFile,
  })

  return (
    <div className="inbox-item">
      <div className="inbox-kind">
        AutoResearchClaw · {isPostExperiment(run.stage) ? 'lab PI decides' : 'project team decides'}
      </div>
      <div className="request-title">
        Stage {w?.stage ?? run.stage}/23 · {(w?.stage_name ?? run.stage_name ?? '').replace(/_/g, ' ').toLowerCase()}
        <span className="chip">{stagePhase(run.stage)}</span>
      </div>
      <p className="inbox-purpose">{run.topic}</p>
      {w?.context_summary && <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, margin: '6px 0' }}>{w.context_summary}</pre>}
      {!!w?.output_files?.length && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', margin: '6px 0' }}>
          {w.output_files.map(p => (
            <button key={p} className="btn" onClick={() => open.mutate(p)} disabled={open.isPending}>{p}</button>
          ))}
        </div>
      )}
      {file && (
        <pre aria-label={file.path} style={{ maxHeight: 300, overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: 12, background: 'var(--surface-input)', padding: 10, borderRadius: 6 }}>
          {file.content}
        </pre>
      )}
      <label className="field">
        <span>Guidance (sent with approve; the reason for a pivot)</span>
        <textarea className="input" rows={2} value={guidance} onChange={e => setGuidance(e.target.value)}
          placeholder="e.g. compress the factorial design to 60 cells; add a paired t-test" />
      </label>
      <div className="inbox-actions">
        <button className="btn btn-primary" disabled={decide.isPending} onClick={() => decide.mutate('approve')}>Approve</button>
        <button className="btn" disabled={decide.isPending} onClick={() => decide.mutate('reject')}>Reject → pivot</button>
        <button className="btn" disabled={decide.isPending} onClick={() => decide.mutate('abort')}>Stop run</button>
      </div>
      {decide.isError && <div className="msg msg-error" role="alert">{(decide.error as Error).message}</div>}
      {open.isError && <div className="msg msg-error" role="alert">{(open.error as Error).message}</div>}
    </div>
  )
}
