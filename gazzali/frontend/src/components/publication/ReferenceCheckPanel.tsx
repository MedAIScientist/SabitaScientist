import { useMutation } from '@tanstack/react-query'
import { api } from '../../api'

const STYLE = {
  verified: { label: 'Verified', color: '#10b981' },
  suspicious: { label: 'Suspicious', color: '#f59e0b' },
  hallucinated: { label: 'Not found', color: '#f43f5e' },
} as const

/**
 * Checks the latest draft's references against CrossRef, OpenAlex, arXiv, PubMed Central
 * and Semantic Scholar. "Suspicious" = the identifier exists but points to another paper.
 */
export function ReferenceCheckPanel({ pubId }: { pubId: string }) {
  const check = useMutation({ mutationFn: () => api.verifyReferences(pubId) })
  const r = check.data
  return (
    <section aria-label="Reference check" style={{ marginBottom: 28 }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 8 }}>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>References</h3>
        <button className="btn" disabled={check.isPending} onClick={() => check.mutate()}>
          {check.isPending ? 'Checking… (about a second per reference)' : 'Check references of the latest draft'}
        </button>
      </div>
      {check.isError && <div className="msg msg-error" role="alert">{(check.error as Error).message}</div>}
      {r && (
        <>
          <p style={{ fontSize: 14, margin: '0 0 6px' }}>
            {r.counts.verified} verified · {r.counts.suspicious} suspicious · {r.counts.hallucinated} not found
          </p>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 6 }}>
            {r.references.map((x, i) => (
              <li key={i} style={{ fontSize: 13, borderLeft: `3px solid ${STYLE[x.status].color}`, paddingLeft: 8 }}>
                <b style={{ color: STYLE[x.status].color }}>{STYLE[x.status].label}</b> · {x.reference}
                {x.matched_title && x.status !== 'verified' && <div style={{ color: 'var(--text-3)' }}>Found instead: {x.matched_title}</div>}
                {x.url && <div><a href={x.url} target="_blank" rel="noreferrer">{x.source}</a></div>}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
