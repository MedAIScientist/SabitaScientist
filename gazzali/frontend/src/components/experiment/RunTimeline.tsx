import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api, ResearchRun, RunStage } from '../../api'
import { PHASES, STAGES, formatDuration } from './stageCatalog'

const STATE_COLOR: Record<string, string> = {
  done: 'var(--accent, #6366f1)', running: '#3b82f6', failed: '#f43f5e', waiting: '#f59e0b', pending: 'var(--border)',
}

function stateOf(stage: number, byNum: Map<number, RunStage>, run: ResearchRun): string {
  const s = byNum.get(stage)
  if (run.status === 'waiting' && run.stage === stage) return 'waiting'
  if (!s) return 'pending'
  if (s.status === 'failed' || s.status === 'rejected') return 'failed'
  return s.status === 'done' || s.status === 'approved' ? 'done' : 'running'
}

/**
 * The run as 23 stages in three phases. A Refine/Pivot or a retried stage is
 * marked, because a failed attempt is evidence too (paper §3.3).
 */
export function RunTimeline({ run }: { run: ResearchRun }) {
  const [selected, setSelected] = useState<number | null>(null)
  const [file, setFile] = useState<{ path: string; content: string } | null>(null)
  const { data } = useQuery({
    queryKey: ['research-stages', run.id],
    queryFn: () => api.researchRunStages(run.id),
    enabled: run.status !== 'queued',
    refetchInterval: run.status === 'running' ? 15_000 : false,
  })
  const open = useMutation({ mutationFn: (path: string) => api.researchRunFile(run.id, path), onSuccess: setFile })
  const byNum = new Map((data?.stages ?? []).map(s => [s.stage, s]))
  const sel = selected != null ? byNum.get(selected) : undefined

  if (run.status === 'queued') {
    return <p style={{ color: 'var(--text-3)' }}>Waiting in the queue{run.queue_position ? ` (position ${run.queue_position})` : ''}. It starts when the current run frees the AI quota.</p>
  }

  return (
    <div>
      {data?.topic_evaluation && (
        <p style={{ fontSize: 13, color: 'var(--text-3)', margin: '4px 0 8px' }}>
          Topic score {data.topic_evaluation.overall}/10 · novelty {data.topic_evaluation.novelty} · specificity {data.topic_evaluation.specificity} · feasibility {data.topic_evaluation.feasibility}
        </p>
      )}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        {PHASES.map(phase => (
          <div key={phase.name} style={{ flex: phase.to - phase.from + 1, minWidth: 180 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: phase.color, marginBottom: 4 }}>{phase.name}</div>
            <div style={{ display: 'flex', gap: 3 }} role="list" aria-label={`${phase.name} stages`}>
              {Array.from({ length: phase.to - phase.from + 1 }, (_, i) => phase.from + i).map(n => {
                const state = stateOf(n, byNum, run)
                const s = byNum.get(n)
                const marker = s && (s.decision === 'pivot' || s.decision === 'refine' || s.attempts > 1)
                return (
                  <button key={n} role="listitem" onClick={() => { setSelected(n); setFile(null) }}
                    title={`${n}. ${STAGES[n].title} — ${state}${s?.duration_sec ? ` (${formatDuration(s.duration_sec)})` : ''}`}
                    aria-label={`Stage ${n}: ${STAGES[n].title}, ${state}`}
                    style={{
                      flex: 1, height: 22, borderRadius: 4, cursor: 'pointer', position: 'relative',
                      background: STATE_COLOR[state], opacity: state === 'pending' ? 0.5 : 1,
                      outline: selected === n ? '2px solid var(--text-heading)' : 'none', border: 'none',
                    }}>
                    {marker && <span style={{ position: 'absolute', top: -7, right: -3, fontSize: 11 }}>↻</span>}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>
      {selected != null && (
        <div style={{ marginTop: 10, padding: 10, border: '1px solid var(--border)', borderRadius: 8 }}>
          <div style={{ fontWeight: 600 }}>{selected}. {STAGES[selected].title}</div>
          <div style={{ fontSize: 13, color: 'var(--text-3)' }}>{STAGES[selected].explain}</div>
          {sel ? (
            <div style={{ fontSize: 13, marginTop: 6 }}>
              {sel.status}{sel.duration_sec ? ` in ${formatDuration(sel.duration_sec)}` : ''}
              {sel.decision && sel.decision !== 'proceed' && <> · decision: <b>{sel.decision}</b></>}
              {sel.attempts > 1 && <> · {sel.attempts} attempts</>}
              {sel.error && <div className="msg msg-error" role="alert" style={{ marginTop: 6 }}>{sel.error}</div>}
              {sel.artifacts.length > 0 && (
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                  {sel.artifacts.map(p => (
                    <button key={p} className="btn" onClick={() => open.mutate(p)} disabled={open.isPending}>{p.split('/').slice(1).join('/')}</button>
                  ))}
                </div>
              )}
            </div>
          ) : <div style={{ fontSize: 13, marginTop: 6, color: 'var(--text-3)' }}>Not reached yet.</div>}
          {file && (
            <pre aria-label={file.path} style={{ maxHeight: 320, overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: 12, background: 'var(--surface-input)', padding: 10, borderRadius: 6, marginTop: 8 }}>{file.content}</pre>
          )}
          {open.isError && <div className="msg msg-error" role="alert">{(open.error as Error).message}</div>}
        </div>
      )}
    </div>
  )
}
