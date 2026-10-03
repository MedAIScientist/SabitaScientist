import { useQuery } from '@tanstack/react-query'
import { aiUsageApi, AiUsageBreakdown } from '../api'

/**
 * What the AI actually consumed, for one paper, one project, or one person.
 *
 * Two honesty rules shape this panel:
 *  - provider-reported tokens and estimates are shown separately, never summed,
 *    because a model that does not report usage must not look measured;
 *  - there is no cost figure. We do not have a maintained price table, and a
 *    made-up number would be worse than no number.
 */
export function AiUsagePanel({
  title = 'AI usage',
  publicationId,
  projectId,
  scope = 'me',
  days = 30,
}: {
  title?: string
  publicationId?: string
  projectId?: string
  scope?: 'me' | 'all'
  days?: number
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['ai-usage', scope, publicationId ?? '', projectId ?? '', days],
    queryFn: () => aiUsageApi.summary({ scope, publication_id: publicationId, project_id: projectId, days }),
  })

  const tokens = data?.tokens
  const measured = tokens?.provider_reported ?? 0
  const estimated = tokens?.estimated ?? 0
  const busiest = data?.by_task?.[0]
  const maxTokens = Math.max(
    1,
    ...(data?.by_task ?? []).map(t => t.provider_tokens + t.estimated_tokens),
  )

  return (
    <section style={{ border: '1px solid var(--border)', borderRadius: 8, background: 'var(--surface-panel)', padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
        <h2 style={{ margin: 0, fontSize: 15, color: 'var(--text-heading)' }}>{title}</h2>
        <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
          LAST {days} DAYS
        </span>
      </div>

      {isLoading && <div style={{ fontSize: 13, color: 'var(--text-2)' }}>Loading…</div>}
      {error && (
        <div style={{ fontSize: 13, color: '#f43f5e' }}>
          Usage could not be read: {(error as Error).message}
        </div>
      )}

      {data && data.calls === 0 && (
        <div style={{ fontSize: 13, color: 'var(--text-2)' }}>
          No AI calls recorded in this window.
        </div>
      )}

      {data && data.calls > 0 && (
        <>
          <div style={{ display: 'flex', gap: 22, flexWrap: 'wrap', marginBottom: 12 }}>
            <Stat label="CALLS" value={String(data.calls)} />
            <Stat label="TOKENS" value={measured.toLocaleString()} />
            {estimated > 0 && <Stat label="ESTIMATED" value={`≈ ${estimated.toLocaleString()}`} muted />}
            {data.avg_duration_ms != null && (
              <Stat label="AVG LATENCY" value={`${(data.avg_duration_ms / 1000).toFixed(1)}s`} muted />
            )}
          </div>

          {estimated > 0 && (
            <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', marginBottom: 12, lineHeight: 1.5 }}>
              TOKENS is what the model reported. ESTIMATED is derived from text length for calls
              where the provider reported nothing — the two are never added together.
            </div>
          )}

          <Breakdown heading="BY TASK" rows={data.by_task} max={maxTokens} />
          <Breakdown heading="BY MODEL" rows={data.by_model} max={maxTokens} />

          {busiest && (
            <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-2)' }}>
              Heaviest task: <strong style={{ color: 'var(--text)' }}>{busiest.label}</strong>{' '}
              ({busiest.calls} call{busiest.calls === 1 ? '' : 's'})
            </div>
          )}
        </>
      )}
    </section>
  )
}

function Stat({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', color: 'var(--text-dim)' }}>
        {label}
      </div>
      <div style={{
        fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
        color: muted ? 'var(--text-2)' : 'var(--text-heading)',
      }}>
        {value}
      </div>
    </div>
  )
}

function Breakdown({ heading, rows, max }: { heading: string; rows: AiUsageBreakdown[]; max: number }) {
  if (!rows.length) return null
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', color: 'var(--text-dim)', marginBottom: 6 }}>
        {heading}
      </div>
      <div style={{ display: 'grid', gap: 5 }}>
        {rows.slice(0, 8).map(row => {
          const total = row.provider_tokens + row.estimated_tokens
          const width = Math.max(2, Math.round((total / max) * 100))
          return (
            <div key={row.label} style={{ display: 'grid', gridTemplateColumns: '1fr 56px 78px', gap: 8, alignItems: 'center' }}>
              <div style={{ position: 'relative', height: 18, background: 'var(--surface-input)', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ position: 'absolute', inset: 0, width: `${width}%`, background: 'rgba(var(--accent-rgb),0.28)' }} />
                <span style={{ position: 'absolute', left: 6, top: 1, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text)' }}>
                  {row.label}
                </span>
              </div>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>
                {row.calls}×
              </span>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-2)', textAlign: 'right' }}>
                {total.toLocaleString()}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
