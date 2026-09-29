import React, { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ExperimentMetric } from '../../api'

const inputStyle: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box', padding: '7px 10px',
  background: 'var(--surface-input)', border: '1px solid var(--border)',
  borderRadius: 6, color: 'var(--text)', fontSize: 18, outline: 'none',
}

function formatValue(m: ExperimentMetric): string {
  const digits = Math.abs(m.value) < 10 ? 4 : 2
  const value = m.value.toLocaleString('en-US', { maximumFractionDigits: digits })
  const base = m.unit ? `${value} ${m.unit}` : value
  return m.stderr == null ? base : `${base} ± ${m.stderr}`
}

/**
 * The numbers paper drafting reads. A results CSV uploaded to a RESULTS entry is
 * parsed into these server-side, so they can already exist for an experiment
 * whose author never typed them — which is why they need a place to be seen.
 */
export function ExperimentMetricsTab({ projectId, experimentId }: {
  projectId: string; experimentId: string
}) {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [value, setValue] = useState('')
  const [unit, setUnit] = useState('')
  const [split, setSplit] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { data: metrics = [], isLoading } = useQuery({
    queryKey: ['experiment-metrics', projectId, experimentId],
    queryFn: () => api.listExperimentMetrics(projectId, experimentId),
  })

  const create = useMutation({
    mutationFn: () => api.createExperimentMetric(projectId, experimentId, {
      name: name.trim(),
      value: Number(value),
      unit: unit.trim() || null,
      split: split.trim() || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['experiment-metrics', projectId, experimentId] })
      setName(''); setValue(''); setUnit(''); setSplit(''); setError(null)
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : 'Could not record the metric'),
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteExperimentMetric(projectId, experimentId, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['experiment-metrics', projectId, experimentId] }),
  })

  const fromUpload = metrics.filter(m => m.source_attachment_id).length
  const canSubmit = name.trim().length > 0 && value !== '' && !Number.isNaN(Number(value))

  return (
    <div>
      <div style={{
        fontSize: 15, color: 'var(--text-dim)', marginBottom: 12, lineHeight: 1.5,
      }}>
        Recorded results. Uploading a results table to a RESULTS entry fills these
        automatically, and drafting takes its numbers from here and nowhere else.
      </div>

      {error && (
        <div style={{
          padding: '7px 10px', marginBottom: 10, background: 'rgba(244,63,94,0.08)',
          border: '1px solid rgba(244,63,94,0.2)', borderRadius: 5,
          color: '#f43f5e', fontSize: 16,
        }}>{error}</div>
      )}

      {/* Manual entry, for numbers that never arrive as a file. */}
      <div style={{
        background: 'var(--surface-2)', border: '1px solid var(--border)',
        borderRadius: 6, padding: 10, marginBottom: 14,
      }}>
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 8, marginBottom: 8 }}>
          <input
            value={name} onChange={e => setName(e.target.value)}
            placeholder="metric name (e.g. dice)" style={inputStyle}
          />
          <input
            value={value} onChange={e => setValue(e.target.value)}
            placeholder="value" inputMode="decimal" style={inputStyle}
          />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <input
            value={unit} onChange={e => setUnit(e.target.value)}
            placeholder="unit (optional)" style={inputStyle}
          />
          <input
            value={split} onChange={e => setSplit(e.target.value)}
            placeholder="split (optional)" style={inputStyle}
          />
        </div>
        <button
          onClick={() => create.mutate()}
          disabled={!canSubmit || create.isPending}
          style={{
            width: '100%', marginTop: 8, padding: '7px 0', borderRadius: 5,
            cursor: canSubmit ? 'pointer' : 'default', border: 'none',
            background: !canSubmit || create.isPending ? 'rgba(255,128,21,0.35)' : '#ff8015',
            color: '#06091a', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
          }}
        >{create.isPending ? 'RECORDING…' : '+ RECORD METRIC'}</button>
      </div>

      {isLoading ? (
        <Muted>LOADING…</Muted>
      ) : metrics.length === 0 ? (
        <Muted>No results recorded yet.</Muted>
      ) : (
        <>
          <div style={{
            fontSize: 13, color: 'var(--text-3)', fontFamily: 'var(--font-mono)',
            marginBottom: 6,
          }}>
            {metrics.length} METRIC{metrics.length === 1 ? '' : 'S'}
            {fromUpload > 0 ? ` · ${fromUpload} FROM UPLOADED RESULTS` : ''}
          </div>
          {metrics.map(m => (
            <div key={m.id} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              background: 'var(--surface-2)', border: '1px solid var(--border)',
              borderRadius: 5, padding: '7px 9px', marginBottom: 5,
            }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 17, color: 'var(--text)' }}>{formatValue(m)}</div>
                <div style={{
                  fontSize: 12, color: 'var(--text-3)', fontFamily: 'var(--font-mono)',
                  marginTop: 1,
                }}>
                  {m.name}
                  {m.split ? ` · ${m.split}` : ''}
                  {m.n != null ? ` · n=${m.n}` : ''}
                  {m.source_attachment_id ? ' · FROM CSV' : ''}
                </div>
              </div>
              <button
                onClick={() => remove.mutate(m.id)}
                style={{
                  cursor: 'pointer', padding: '4px 9px', borderRadius: 4,
                  background: 'transparent', border: '1px solid rgba(244,63,94,0.3)',
                  color: '#f43f5e', fontSize: 13,
                  fontFamily: 'var(--font-mono)', fontWeight: 700,
                }}
              >✕</button>
            </div>
          ))}
        </>
      )}
    </div>
  )
}

function Muted({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      padding: '16px 0', color: 'var(--text-dim)',
      fontFamily: 'var(--font-mono)', fontSize: 15,
    }}>{children}</div>
  )
}
