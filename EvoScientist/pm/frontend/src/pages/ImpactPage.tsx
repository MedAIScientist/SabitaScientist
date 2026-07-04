import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, LabImpact } from '../api'
import { useAuth } from '../auth'

export function ImpactPage() {
  const { id: labId } = useParams<{ id: string }>()
  const { token } = useAuth()
  const [impact, setImpact] = useState<LabImpact | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!labId || !token) return
    setLoading(true)
    api.labResearchImpact(labId)
      .then(setImpact)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [labId, token])

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 19 }}>LOADING…</div>
  if (error) return <div style={{ padding: 40, color: '#f43f5e' }}>{error}</div>
  if (!impact) return null

  const card: React.CSSProperties = {
    background: 'var(--surface-card)', border: '1px solid var(--border)',
    borderRadius: 10, padding: '18px 20px', textAlign: 'center',
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <div style={{ maxWidth: 800, margin: '0 auto', padding: '32px 28px' }}>
        <h1 style={{ margin: '0 0 6px', fontSize: 30, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>
          Research Impact: {impact.lab_name}
        </h1>
        <p style={{ margin: '0 0 24px', fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
          {impact.member_count} members · {impact.total_publications} publications · {impact.s2_matched} matched in Semantic Scholar
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 28 }}>
          <div style={card}><div style={{ fontSize: 36, fontWeight: 700, color: '#ff8015', fontFamily: 'var(--font-mono)' }}>{impact.total_citations}</div><div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>CITATIONS</div></div>
          <div style={card}><div style={{ fontSize: 36, fontWeight: 700, color: '#6366f1', fontFamily: 'var(--font-mono)' }}>{impact.h_index}</div><div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>H-INDEX</div></div>
          <div style={card}><div style={{ fontSize: 36, fontWeight: 700, color: '#10b981', fontFamily: 'var(--font-mono)' }}>{impact.average_citations_per_paper}</div><div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>AVG CITATIONS</div></div>
          <div style={card}><div style={{ fontSize: 36, fontWeight: 700, color: '#f59e0b', fontFamily: 'var(--font-mono)' }}>{impact.total_publications}</div><div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>PAPERS</div></div>
        </div>

        {/* Publications by status */}
        <h2 style={{ margin: '0 0 12px', fontSize: 22, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>Publications by Status</h2>
        <div style={{ display: 'flex', gap: 8, marginBottom: 28, flexWrap: 'wrap' }}>
          {Object.entries(impact.publications_by_status).map(([status, count]) => (
            <span key={status} style={{
              fontSize: 15, fontFamily: 'var(--font-mono)', fontWeight: 700,
              background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)',
              borderRadius: 6, padding: '4px 12px',
            }}>{status.toUpperCase()}: {count}</span>
          ))}
        </div>

        {/* Publications with S2 data */}
        <h2 style={{ margin: '0 0 12px', fontSize: 22, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>
          Publications ({impact.publications.length})
        </h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {impact.publications.map((p, i) => (
            <div key={i} style={{
              background: 'var(--surface-card)', border: '1px solid var(--border)',
              borderRadius: 8, padding: '12px 16px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 18, fontWeight: 500, color: 'var(--text-heading)' }}>{p.title}</div>
                  <div style={{ fontSize: 15, color: 'var(--text-dim)', marginTop: 2 }}>
                    {p.venue} · {p.year || '?'} · {p.fields?.slice(0, 2).join(', ') || ''}
                  </div>
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 12 }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: '#ff8015', fontFamily: 'var(--font-mono)' }}>{p.citations}</div>
                  <div style={{ fontSize: 13, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>citations</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
