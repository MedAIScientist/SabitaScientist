import React, { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ExperimentMetric } from '../../api'

const inputStyle: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box', padding: '7px 10px',
  background: 'var(--surface-input)', border: '1px solid var(--border)',
  borderRadius: 6, color: 'var(--text)', fontSize: 15, outline: 'none',
}

const SOURCE_TEXT: Record<string, string> = { manual: 'typed in', csv: 'from table', cvat: 'from CVAT', ai_run: 'from AI run' }

type Parsed = Awaited<ReturnType<typeof api.importMetricsCsv>>['metrics']

/** Upload a results table: preview what was understood, then save. Nothing is guessed. */
function CsvImport({ projectId, experimentId, onSaved }: { projectId: string; experimentId: string; onSaved: () => void }) {
  const [text, setText] = useState<string | null>(null)
  const [preview, setPreview] = useState<Parsed | null>(null)
  const [error, setError] = useState<string | null>(null)
  const run = useMutation({
    mutationFn: ({ csv, save }: { csv: string; save: boolean }) => api.importMetricsCsv(projectId, experimentId, csv, save),
    onSuccess: (r, { save }) => {
      if (save) { setText(null); setPreview(null); onSaved(); return }
      setPreview(r.metrics)
      setError(r.metrics.length ? null : 'No numbers found. Use a column for the metric name and one for the value, or one numeric column per metric.')
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : 'Could not read the file'),
  })
  const pick = async (f: File | undefined) => {
    if (!f) return
    const csv = await new Promise<string>((resolve, reject) => {
      const r = new FileReader()
      r.onload = () => resolve(String(r.result))
      r.onerror = () => reject(r.error)
      r.readAsText(f)
    }).catch(() => null)
    if (csv == null) { setError('Could not read the file'); return }
    setText(csv)
    run.mutate({ csv, save: false })
  }
  return (
    <div style={{ marginBottom: 14 }}>
      <label className="btn" style={{ display: 'inline-block', cursor: 'pointer' }}>
        ⬆ Upload results table (CSV)
        <input type="file" accept=".csv,.tsv,text/csv" aria-label="Results table file" style={{ display: 'none' }}
          onChange={e => { pick(e.target.files?.[0]); e.target.value = '' }} />
      </label>
      {error && <div role="alert" style={{ color: '#f43f5e', fontSize: 14, marginTop: 6 }}>{error}</div>}
      {preview && preview.length > 0 && text && (
        <div style={{ marginTop: 8, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 6, padding: 10 }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Found {preview.length} number{preview.length === 1 ? '' : 's'}. Check before saving:</div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14, maxHeight: 180, overflow: 'auto' }}>
            {preview.map((m, i) => <li key={i}>{m.name}{m.split ? ` (${m.split})` : ''}: <b>{m.value}</b>{m.unit ? ` ${m.unit}` : ''}{m.stderr != null ? ` ± ${m.stderr}` : ''}</li>)}
          </ul>
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            <button className="btn btn-primary" disabled={run.isPending} onClick={() => run.mutate({ csv: text, save: true })}>Save {preview.length} numbers</button>
            <button className="btn" onClick={() => { setText(null); setPreview(null) }}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  )
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
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', marginBottom: 2 }}>Measured numbers</div>
      <div style={{ fontSize: 14, color: 'var(--text-dim)', marginBottom: 10, lineHeight: 1.5 }}>
        Paper drafts only use numbers recorded here, so the AI never invents results.
        Type them in one by one, or upload a results table (CSV).
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
            placeholder="What did you measure? (e.g. AUC)" aria-label="What did you measure" style={inputStyle}
          />
          <input
            value={value} onChange={e => setValue(e.target.value)}
            placeholder="Value (e.g. 0.91)" aria-label="Value" inputMode="decimal" style={inputStyle}
          />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <input
            value={unit} onChange={e => setUnit(e.target.value)}
            placeholder="Unit (e.g. %, mm) — optional" aria-label="Unit" style={inputStyle}
          />
          <input
            value={split} onChange={e => setSplit(e.target.value)}
            placeholder="Group or data split — optional" aria-label="Group" style={inputStyle}
          />
        </div>
        <button
          onClick={() => create.mutate()}
          disabled={!canSubmit || create.isPending}
          style={{
            width: '100%', marginTop: 8, padding: '7px 0', borderRadius: 5,
            cursor: canSubmit ? 'pointer' : 'default', border: 'none',
            background: !canSubmit || create.isPending ? 'rgba(var(--accent-rgb),0.35)' : 'var(--accent)',
            color: '#fff', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
          }}
        >{create.isPending ? 'Saving…' : '+ Add this number'}</button>
      </div>

      <CsvImport projectId={projectId} experimentId={experimentId}
        onSaved={() => qc.invalidateQueries({ queryKey: ['experiment-metrics', projectId, experimentId] })} />

      {isLoading ? (
        <Muted>Loading…</Muted>
      ) : metrics.length === 0 ? (
        <Muted>No numbers yet. Results drafts will say “not recorded” until you add some.</Muted>
      ) : (
        <>
          <div style={{
            fontSize: 13, color: 'var(--text-3)', fontFamily: 'var(--font-mono)',
            marginBottom: 6,
          }}>
            {metrics.length} number{metrics.length === 1 ? '' : 's'}
            {fromUpload > 0 ? ` · ${fromUpload} from uploaded tables` : ''}
          </div>
          {metrics.map(m => (
            <div key={m.id} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              background: 'var(--surface-2)', border: '1px solid var(--border)',
              borderRadius: 5, padding: '7px 9px', marginBottom: 5,
            }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 15, color: 'var(--text)' }}>{formatValue(m)}</div>
                <div style={{
                  fontSize: 12, color: 'var(--text-3)', fontFamily: 'var(--font-mono)',
                  marginTop: 1,
                }}>
                  {m.name}
                  {m.split ? ` · ${m.split}` : ''}
                  {m.n != null ? ` · n=${m.n}` : ''}
                  {m.source ? ` · ${SOURCE_TEXT[m.source] ?? m.source}` : m.source_attachment_id ? ' · from table' : ''}
                </div>
              </div>
              <button
                onClick={() => remove.mutate(m.id)} aria-label={`Remove ${m.name}`} title="Remove"
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
