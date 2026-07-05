import React, { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Publication_ } from '../api'

const STATUS_COLORS: Record<string, string> = {
  draft: '#6b7280', submitted: '#6366f1', reviewing: '#f59e0b',
  accepted: '#10b981', published: '#059669', rejected: '#f43f5e',
}

export function PublicationsPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const projectFilter = searchParams.get('project_id')
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newVenue, setNewVenue] = useState('')
  const [newVenueType, setNewVenueType] = useState('journal')

  const { data: pubs = [], isLoading } = useQuery({
    queryKey: ['publications', projectFilter],
    queryFn: () => api.listPublications(projectFilter || undefined),
  })

  const createMutation = useMutation({
    mutationFn: () => api.createPublication({
      title: newTitle, venue: newVenue || undefined,
      venue_type: newVenueType,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['publications'] })
      setShowForm(false); setNewTitle(''); setNewVenue('')
    },
  })

  const inputStyle: React.CSSProperties = {
    padding: '9px 12px', background: 'var(--surface-input)',
    border: '1px solid var(--border)', borderRadius: 7,
    color: 'var(--text)', fontSize: 22, outline: 'none', width: '100%',
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <div style={{ maxWidth: 760, margin: '0 auto', padding: '32px 28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 30, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>
              Publications
            </h1>
            <p style={{ margin: '4px 0 0', fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
              {pubs.length} PUBLICATION{pubs.length !== 1 ? 'S' : ''}
            </p>
          </div>
          <button onClick={() => setShowForm(f => !f)} style={{
            cursor: 'pointer', padding: '7px 16px',
            background: 'rgba(255,128,21,0.1)',
            border: '1px solid rgba(255,128,21,0.3)',
            borderRadius: 7, color: '#ff8015',
            fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)',
            letterSpacing: '0.08em',
          }}>+ NEW</button>
        </div>

        {showForm && (
          <form onSubmit={e => { e.preventDefault(); createMutation.mutate() }} style={{
            background: 'var(--surface-card)', border: '1px solid rgba(255,128,21,0.2)',
            borderRadius: 10, padding: 24, marginBottom: 24,
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 14, marginBottom: 14 }}>
              <div>
                <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.1em', fontFamily: 'var(--font-mono)' }}>TITLE *</label>
                <input value={newTitle} onChange={e => setNewTitle(e.target.value)} required style={inputStyle} />
              </div>
              <div>
                <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.1em', fontFamily: 'var(--font-mono)' }}>VENUE TYPE</label>
                <select value={newVenueType} onChange={e => setNewVenueType(e.target.value)} style={inputStyle}>
                  <option value="journal">Journal</option>
                  <option value="conference">Conference</option>
                  <option value="preprint">Preprint</option>
                  <option value="other">Other</option>
                </select>
              </div>
            </div>
            <div style={{ marginBottom: 20 }}>
              <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.1em', fontFamily: 'var(--font-mono)' }}>VENUE</label>
              <input value={newVenue} onChange={e => setNewVenue(e.target.value)} placeholder="e.g. Nature, NeurIPS 2026" style={inputStyle} />
            </div>
            <button type="submit" disabled={createMutation.isPending} style={{
              padding: '9px 24px', cursor: 'pointer',
              background: '#ff8015', color: '#06091a',
              border: 'none', borderRadius: 7, fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)',
            }}>{createMutation.isPending ? 'CREATING…' : 'CREATE'}</button>
          </form>
        )}

        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 19 }}>LOADING…</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {pubs.map(p => (
              <div key={p.id}
                onClick={() => navigate(`/publications/${p.id}`)}
                style={{
                  background: 'var(--surface-card)', border: '1px solid var(--border)',
                  borderRadius: 10, padding: '16px 20px', cursor: 'pointer',
                  transition: 'border-color 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(255,128,21,0.2)' }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-heading)', marginBottom: 4 }}>{p.title}</div>
                    <div style={{ fontSize: 17, color: 'var(--text-2)', marginBottom: 4 }}>
                      {p.venue || 'No venue'}
                      {p.venue_type !== 'journal' && ` (${p.venue_type})`}
                    </div>
                    <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                      {p.authors?.length ? `${p.authors.length} author${p.authors.length > 1 ? 's' : ''}` : 'No authors'} ·
                      {p.project_name ? `${p.project_name} · ` : ''}
                      created {new Date(p.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <span style={{
                    fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)',
                    color: STATUS_COLORS[p.status] || '#6b7280',
                    background: `${STATUS_COLORS[p.status] || '#6b7280'}14`,
                    border: `1px solid ${STATUS_COLORS[p.status] || '#6b7280'}30`,
                    borderRadius: 4, padding: '2px 8px', whiteSpace: 'nowrap',
                    letterSpacing: '0.06em',
                  }}>{p.status.toUpperCase()}</span>
                </div>
              </div>
            ))}
            {pubs.length === 0 && !showForm && (
              <p style={{ color: 'var(--text-muted)', fontSize: 21, padding: '20px 0' }}>
                No publications yet. Start by adding one.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
