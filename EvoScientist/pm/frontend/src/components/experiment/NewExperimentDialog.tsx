import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Experiment, ProjectPhase } from '../../api'

/**
 * One place to create an experiment, used from the experiments page and the board.
 *
 * The old flow asked for a name only, so a new experiment always landed in the
 * board's "Unassigned" lane and had to be edited straight afterwards just to say
 * which phase it belongs to. The phase is therefore part of this form — but
 * hypothesis stays behind a toggle, so the fast path is still "type a name, Enter".
 */
export function NewExperimentDialog({
  projectId,
  phases = [],
  defaultPhaseId,
  onCreated,
  onClose,
}: {
  projectId: string
  phases?: ProjectPhase[]
  defaultPhaseId?: string | null
  onCreated: (experiment: Experiment) => void
  onClose: () => void
}) {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [phaseId, setPhaseId] = useState(defaultPhaseId ?? '')
  const [hypothesis, setHypothesis] = useState('')
  const [showHypothesis, setShowHypothesis] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: () => api.createExperiment(projectId, {
      name: name.trim(),
      phase_id: phaseId || null,
      hypothesis: hypothesis.trim() || null,
    }),
    onSuccess: (experiment) => {
      qc.invalidateQueries({ queryKey: ['experiments', projectId] })
      onCreated(experiment)
    },
    onError: (e: unknown) =>
      setError(e instanceof Error ? e.message : 'Could not create the experiment'),
  })

  const accent = '#10b981'
  const canSubmit = name.trim().length > 0 && !create.isPending

  const field: React.CSSProperties = {
    width: '100%', boxSizing: 'border-box', padding: '8px 10px',
    background: 'var(--surface-input)', border: '1px solid rgba(16,185,129,0.2)',
    borderRadius: 5, color: 'var(--text)', fontSize: 16,
    fontFamily: 'inherit', outline: 'none',
  }
  const label: React.CSSProperties = {
    fontSize: 13, fontWeight: 700, color: 'var(--text-dim)',
    fontFamily: 'var(--font-mono)', letterSpacing: '0.04em',
    display: 'block', marginBottom: 4,
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50,
      }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div style={{
        background: 'var(--surface-panel)', border: '1px solid rgba(16,185,129,0.22)',
        borderRadius: 10, padding: 24, width: 400,
        animation: 'fadeInUp 0.15s ease',
      }}>
        <div style={{
          fontSize: 16, fontWeight: 700, color: accent,
          fontFamily: 'var(--font-mono)', marginBottom: 16, letterSpacing: '0.04em',
        }}>⚗ New experiment</div>

        {error && (
          <div style={{
            padding: '7px 10px', marginBottom: 12, background: 'rgba(244,63,94,0.08)',
            border: '1px solid rgba(244,63,94,0.2)', borderRadius: 5,
            color: '#f43f5e', fontSize: 16,
          }}>{error}</div>
        )}

        <label style={label}>
          Name
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="e.g. Denoise cohort"
            autoFocus
            onKeyDown={e => { if (e.key === 'Enter' && canSubmit) create.mutate() }}
            style={{ ...field, marginTop: 4 }}
          />
        </label>

        <label style={{ ...label, marginTop: 14 }}>
          Phase
          <select
            value={phaseId}
            onChange={e => setPhaseId(e.target.value)}
            style={{ ...field, marginTop: 4 }}
          >
            <option value="">No phase (appears unassigned on the board)</option>
            {phases.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        {phases.length === 0 && (
          <div style={{
            fontSize: 13, color: 'var(--text-3)', fontFamily: 'var(--font-mono)',
            marginTop: 4,
          }}>
            This project has no phases yet — add them from the board.
          </div>
        )}

        {showHypothesis ? (
          <label style={{ ...label, marginTop: 14 }}>
            Hypothesis
            <textarea
              value={hypothesis}
              onChange={e => setHypothesis(e.target.value)}
              rows={3}
              placeholder="What do you expect to find?"
              style={{ ...field, marginTop: 4, resize: 'vertical' }}
            />
          </label>
        ) : (
          <button
            onClick={() => setShowHypothesis(true)}
            style={{
              marginTop: 12, cursor: 'pointer', padding: '4px 0',
              background: 'none', border: 'none', color: 'var(--text-muted)',
              fontSize: 15, fontFamily: 'var(--font-mono)',
            }}
          >＋ add hypothesis (optional)</button>
        )}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 18 }}>
          <button
            onClick={onClose}
            style={{
              background: 'var(--surface-input)', border: '1px solid var(--border-subtle)',
              borderRadius: 4, padding: '6px 14px', color: 'var(--text-muted)',
              fontSize: 16, cursor: 'pointer', fontFamily: 'var(--font-mono)',
            }}
          >Cancel</button>
          <button
            onClick={() => create.mutate()}
            disabled={!canSubmit}
            style={{
              background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.28)',
              borderRadius: 4, padding: '6px 14px', color: accent,
              fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
              cursor: canSubmit ? 'pointer' : 'default',
              opacity: canSubmit ? 1 : 0.4,
            }}
          >{create.isPending ? 'CREATING…' : 'CREATE'}</button>
        </div>
      </div>
    </div>
  )
}
