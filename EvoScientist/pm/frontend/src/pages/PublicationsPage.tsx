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

  const deleteMutation = useMutation({
    mutationFn: (pubId: string) => api.deletePublication(pubId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['publications'] }),
  })

  const inputStyle: React.CSSProperties = {
    padding: '9px 12px', background: 'var(--surface-input)',
    border: '1px solid var(--border)', borderRadius: 7,
    color: 'var(--text)', fontSize: 17, outline: 'none', width: '100%',
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>
              Publications
            </h1>
            <p style={{ margin: '4px 0 0', fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
              {pubs.length} publication{pubs.length !== 1 ? 's' : ''}
            </p>
          </div>
          <button onClick={() => setShowForm(f => !f)} className="btn btn-primary">+ New paper</button>
        </div>

        {showForm && (
          <form onSubmit={e => { e.preventDefault(); createMutation.mutate() }} style={{
            background: 'var(--surface-card)', border: '1px solid rgba(var(--accent-rgb),0.2)',
            borderRadius: 10, padding: 24, marginBottom: 24,
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 14, marginBottom: 14 }}>
              <div>
                <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.04em', fontFamily: 'var(--font-mono)' }}>Title *</label>
                <input value={newTitle} onChange={e => setNewTitle(e.target.value)} required style={inputStyle} />
              </div>
              <div>
                <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.04em', fontFamily: 'var(--font-mono)' }}>Venue type</label>
                <select value={newVenueType} onChange={e => setNewVenueType(e.target.value)} style={inputStyle}>
                  <option value="journal">Journal</option>
                  <option value="conference">Conference</option>
                  <option value="preprint">Preprint</option>
                  <option value="other">Other</option>
                </select>
              </div>
            </div>
            <div style={{ marginBottom: 20 }}>
              <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.04em', fontFamily: 'var(--font-mono)' }}>Venue</label>
              <input value={newVenue} onChange={e => setNewVenue(e.target.value)} placeholder="e.g. Nature, NeurIPS 2026" style={inputStyle} />
            </div>
            <button type="submit" disabled={createMutation.isPending} style={{
              padding: '9px 24px', cursor: 'pointer',
              background: 'var(--accent)', color: '#fff',
              border: 'none', borderRadius: 7, fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
            }}>{createMutation.isPending ? 'Creating…' : 'Create'}</button>
          </form>
        )}

        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 16 }}>Loading…</div>
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
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(var(--accent-rgb),0.2)' }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 17, fontWeight: 600, color: 'var(--text-heading)', marginBottom: 4 }}>{p.title}</div>
                    <div style={{ fontSize: 15, color: 'var(--text-2)', marginBottom: 4 }}>
                      {p.venue || 'No venue'}
                      {p.venue_type !== 'journal' && ` (${p.venue_type})`}
                    </div>
                    <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                      {p.authors?.length ? `${p.authors.length} author${p.authors.length > 1 ? 's' : ''}` : 'No authors'} ·
                      {p.project_name ? `${p.project_name} · ` : ''}
                      created {new Date(p.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
                    <span style={{
                      fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)',
                      color: STATUS_COLORS[p.status] || '#6b7280',
                      background: `${STATUS_COLORS[p.status] || '#6b7280'}14`,
                      border: `1px solid ${STATUS_COLORS[p.status] || '#6b7280'}30`,
                      borderRadius: 4, padding: '2px 8px', whiteSpace: 'nowrap',
                      letterSpacing: '0.04em',
                    }}>{p.status.toUpperCase()}</span>
                    <button onClick={e => { e.stopPropagation(); if (confirm('Delete this publication?')) deleteMutation.mutate(p.id) }}
                      style={{
                        cursor: 'pointer', padding: '3px 10px', fontSize: 13, fontWeight: 700,
                        fontFamily: 'var(--font-mono)',
                        background: 'rgba(244,63,94,0.06)', border: '1px solid rgba(244,63,94,0.15)',
                        borderRadius: 4, color: '#f43f5e', transition: 'background 0.14s',
                      }}
                      onMouseEnter={e => { e.currentTarget.style.background = 'rgba(244,63,94,0.14)' }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'rgba(244,63,94,0.06)' }}
                    >Delete</button>
                  </div>
                </div>
              </div>
            ))}
            {pubs.length === 0 && !showForm && (
              <p style={{ color: 'var(--text-muted)', fontSize: 17, padding: '20px 0' }}>
                No publications yet. Start by adding one.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
