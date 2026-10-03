import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, GateAction, ResearchRun } from '../../api'
import { STAGES, quickReplies, stageTitle } from './stageCatalog'

/** From result analysis on, a PI of the lab decides (plan §4.1). */
export const isPostExperiment = (stage: number | null) => stage != null && stage >= 14

const QUALITY_GATE = 20

/** One AutoResearchClaw gate waiting for a human: what it produced, and the decision. */
export function ResearchGateCard({ run }: { run: ResearchRun }) {
  const qc = useQueryClient()
  const [guidance, setGuidance] = useState('')
  const [quality, setQuality] = useState<number | ''>('')
  const w = run.waiting
  const stage = w?.stage ?? run.stage
  const info = stage ? STAGES[stage] : undefined
  const files = w?.output_files ?? []
  const [path, setPath] = useState<string | null>(files[0] ?? null)
  const preview = useQuery({
    queryKey: ['research-file', run.id, path],
    queryFn: () => api.researchRunFile(run.id, path!),
    enabled: !!path,
  })
  const decide = useMutation({
    mutationFn: (action: GateAction) => api.respondResearchGate(run.id, {
      action, guidance, message: guidance,
      ...(stage === QUALITY_GATE && quality !== '' ? { quality } : {}),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['research-gates'] })
      qc.invalidateQueries({ queryKey: ['research-runs', run.experiment_id] })
    },
  })
  const addChip = (text: string) => setGuidance(g => (g ? `${g}; ${text}` : text))

  return (
    <div className="inbox-item">
      <div className="inbox-kind">
        AutoResearchClaw · {isPostExperiment(stage) ? 'a PI of the lab decides' : 'the project team decides'}
      </div>
      <div className="request-title">
        {stage}/23 · {stageTitle(stage)}
        {info && <span className="chip">{info.phase}</span>}
      </div>
      {info && <p style={{ fontSize: 13, color: 'var(--text-3)', margin: '2px 0 6px' }}>{info.explain}</p>}
      <p className="inbox-purpose">{run.topic}</p>
      {w?.context_summary && <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, margin: '6px 0' }}>{w.context_summary}</pre>}
      {files.length > 1 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', margin: '6px 0' }}>
          {files.map(p => (
            <button key={p} className="btn" aria-pressed={p === path} onClick={() => setPath(p)}>{p.split('/').pop()}</button>
          ))}
        </div>
      )}
      {path && (
        <pre aria-label={path} style={{ maxHeight: 260, overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: 12, background: 'var(--surface-input)', padding: 10, borderRadius: 6 }}>
          {preview.isLoading ? 'Loading…' : preview.data?.content ?? (preview.isError ? 'Could not load this file.' : '')}
        </pre>
      )}
      <label className="field">
        <span>Guidance (sent with approve; the reason for a pivot)</span>
        <textarea className="input" rows={2} value={guidance} onChange={e => setGuidance(e.target.value)}
          placeholder="e.g. compress the factorial design to 60 cells; add a paired t-test" />
      </label>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', margin: '4px 0 8px' }} aria-label="Quick replies">
        {quickReplies(stage).map(t => (
          <button key={t} type="button" className="chip" style={{ cursor: 'pointer' }} onClick={() => addChip(t)}>+ {t}</button>
        ))}
      </div>
      {stage === QUALITY_GATE && (
        <label className="field" style={{ maxWidth: 260 }}>
          <span>Your quality score for this run (1–10, optional)</span>
          <input className="input" type="number" min={1} max={10} value={quality}
            onChange={e => setQuality(e.target.value === '' ? '' : Math.max(1, Math.min(10, Number(e.target.value))))} />
        </label>
      )}
      <div className="inbox-actions">
        <button className="btn btn-primary" disabled={decide.isPending} onClick={() => decide.mutate('approve')}>Approve</button>
        <button className="btn" disabled={decide.isPending} onClick={() => decide.mutate('reject')}>Reject → pivot</button>
        <button className="btn" disabled={decide.isPending} onClick={() => decide.mutate('abort')}>Stop run</button>
      </div>
      {decide.isError && <div className="msg msg-error" role="alert">{(decide.error as Error).message}</div>}
    </div>
  )
}
