import React, { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Publication_, Version, Review } from '../api'

const STATUS_OPTIONS = ['draft', 'submitted', 'reviewing', 'accepted', 'published', 'rejected']
const STATUS_COLORS: Record<string, string> = {
  draft: '#6b7280', submitted: '#6366f1', reviewing: '#f59e0b',
  accepted: '#10b981', published: '#059669', rejected: '#f43f5e',
}

export function PublicationDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState('')
  const [editVenue, setEditVenue] = useState('')
  const [editAbstract, setEditAbstract] = useState('')
  const [editDoi, setEditDoi] = useState('')
  const [showNewVersion, setShowNewVersion] = useState(false)
  const [versionNotes, setVersionNotes] = useState('')
  const [showNewReview, setShowNewReview] = useState(false)
  const [reviewerName, setReviewerName] = useState('')
  const [reviewComments, setReviewComments] = useState('')
  const [reviewDecision, setReviewDecision] = useState('')

  const { data: pub, isLoading } = useQuery({
    queryKey: ['publication', id],
    queryFn: () => api.getPublication(id!),
    enabled: Boolean(id),
  })

  const { data: versions = [] } = useQuery({
    queryKey: ['versions', id],
    queryFn: () => api.listVersions(id!),
    enabled: Boolean(id),
  })

  const { data: reviews = [] } = useQuery({
    queryKey: ['reviews', id],
    queryFn: () => api.listReviews(id!),
    enabled: Boolean(id),
  })

  const updateMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.updatePublication(id!, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['publication', id] }); setEditing(false) },
  })

  const submitMutation = useMutation({
    mutationFn: () => api.submitPublication(id!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['publication', id] }),
  })

  const versionMutation = useMutation({
    mutationFn: () => api.createVersion(id!, versionNotes || undefined),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['versions', id] }); setShowNewVersion(false); setVersionNotes('') },
  })

  const reviewMutation = useMutation({
    mutationFn: () => api.createReview(id!, {
      reviewer_name: reviewerName || undefined,
      comments: reviewComments || undefined,
      decision: reviewDecision || undefined,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['reviews', id] }); setShowNewReview(false); setReviewerName(''); setReviewComments(''); setReviewDecision('') },
  })

  if (isLoading || !pub) return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', padding: 40, fontFamily: 'var(--font-mono)', fontSize: 19 }}>
      LOADING…
    </div>
  )

  const inputStyle: React.CSSProperties = {
    padding: '9px 12px', background: 'var(--surface-input)',
    border: '1px solid var(--border)', borderRadius: 7,
    color: 'var(--text)', fontSize: 22, outline: 'none', width: '100%',
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <div style={{ maxWidth: 760, margin: '0 auto', padding: '32px 28px' }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
          <div style={{ flex: 1, marginRight: 20 }}>
            {editing ? (
              <input value={editTitle} onChange={e => setEditTitle(e.target.value)} style={inputStyle} />
            ) : (
              <h1 style={{ margin: 0, fontSize: 28, fontWeight: 600, color: 'var(--text-heading)', lineHeight: 1.3 }}>
                {pub.title}
              </h1>
            )}
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <span style={{
                fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)',
                color: STATUS_COLORS[pub.status] || '#6b7280',
                background: `${STATUS_COLORS[pub.status] || '#6b7280'}14`,
                border: `1px solid ${STATUS_COLORS[pub.status] || '#6b7280'}30`,
                borderRadius: 4, padding: '2px 8px', letterSpacing: '0.06em',
              }}>{pub.status.toUpperCase()}</span>
              <span style={{
                fontSize: 14, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)',
                padding: '2px 0',
              }}>{pub.venue_type.toUpperCase()}</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {pub.status === 'draft' && (
              <button onClick={() => submitMutation.mutate()} style={{
                cursor: 'pointer', padding: '7px 14px',
                background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.3)',
                borderRadius: 7, color: '#6366f1', fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
              }}>SUBMIT</button>
            )}
            <button onClick={() => {
              if (!editing) { setEditTitle(pub.title); setEditVenue(pub.venue || ''); setEditAbstract(pub.abstract || ''); setEditDoi(pub.doi || '') }
              setEditing(e => !e)
            }} style={{
              cursor: 'pointer', padding: '7px 14px',
              background: 'rgba(255,128,21,0.1)', border: '1px solid rgba(255,128,21,0.3)',
              borderRadius: 7, color: '#ff8015', fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
            }}>{editing ? 'CANCEL' : 'EDIT'}</button>
          </div>
        </div>

        {/* Edit form */}
        {editing && (
          <div style={{ background: 'var(--surface-card)', border: '1px solid rgba(255,128,21,0.2)', borderRadius: 10, padding: 24, marginBottom: 24 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
              <div>
                <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>VENUE</label>
                <input value={editVenue} onChange={e => setEditVenue(e.target.value)} style={inputStyle} />
              </div>
              <div>
                <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>DOI</label>
                <input value={editDoi} onChange={e => setEditDoi(e.target.value)} placeholder="10.xxxx/xxxxx" style={inputStyle} />
              </div>
            </div>
            <div style={{ marginBottom: 14 }}>
              <label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>ABSTRACT</label>
              <textarea value={editAbstract} onChange={e => setEditAbstract(e.target.value)} rows={4} style={{ ...inputStyle, resize: 'vertical' }} />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {STATUS_OPTIONS.map(s => (
                <button key={s} onClick={() => updateMutation.mutate({ status: s })} style={{
                  cursor: 'pointer', padding: '4px 10px', fontSize: 14, fontFamily: 'var(--font-mono)', fontWeight: 700,
                  background: pub.status === s ? `${STATUS_COLORS[s]}20` : 'transparent',
                  border: `1px solid ${STATUS_COLORS[s]}40`,
                  borderRadius: 4, color: STATUS_COLORS[s],
                }}>{s.toUpperCase()}</button>
              ))}
            </div>
            <button onClick={() => updateMutation.mutate({ title: editTitle, venue: editVenue || null, abstract: editAbstract || null, doi: editDoi || null })}
              style={{ marginTop: 14, padding: '9px 24px', cursor: 'pointer', background: '#ff8015', color: '#06091a', border: 'none', borderRadius: 7, fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
              SAVE
            </button>
          </div>
        )}

        {/* Info */}
        {!editing && pub.abstract && (
          <div style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: 20, marginBottom: 24 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginBottom: 8 }}>ABSTRACT</div>
            <p style={{ margin: 0, fontSize: 19, color: 'var(--text-2)', lineHeight: 1.6 }}>{pub.abstract}</p>
          </div>
        )}

        {!editing && (
          <div style={{ display: 'flex', gap: 24, marginBottom: 24, fontSize: 17, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
            {pub.venue && <span>Venue: {pub.venue}</span>}
            {pub.doi && <span>DOI: {pub.doi}</span>}
            {pub.url && <span><a href={pub.url} target="_blank" style={{ color: '#6366f1' }}>URL</a></span>}
          </div>
        )}

        {/* Versions */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>
            Versions ({versions.length})
          </h2>
          <button onClick={() => setShowNewVersion(true)} style={{
            cursor: 'pointer', padding: '5px 12px',
            background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)',
            borderRadius: 6, color: '#10b981', fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
          }}>+ NEW</button>
        </div>

        {showNewVersion && (
          <div style={{ background: 'var(--surface-card)', border: '1px solid rgba(16,185,129,0.2)', borderRadius: 10, padding: 16, marginBottom: 12 }}>
            <textarea value={versionNotes} onChange={e => setVersionNotes(e.target.value)} placeholder="Version notes…" rows={2}
              style={{ ...inputStyle, marginBottom: 8, resize: 'vertical' }} />
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => versionMutation.mutate()} style={{ padding: '6px 16px', cursor: 'pointer', background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.28)', borderRadius: 6, color: '#10b981', fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>CREATE VERSION</button>
              <button onClick={() => setShowNewVersion(false)} style={{ padding: '6px 12px', cursor: 'pointer', background: 'transparent', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-muted)', fontSize: 16 }}>CANCEL</button>
            </div>
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 32 }}>
          {versions.map(v => (
            <div key={v.id} style={{
              background: 'var(--surface-card)', border: '1px solid var(--border)',
              borderRadius: 8, padding: '12px 16px', display: 'flex', justifyContent: 'space-between',
            }}>
              <div>
                <span style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', fontSize: 17 }}>v{v.version}</span>
                {v.notes && <span style={{ color: 'var(--text-2)', marginLeft: 12 }}>{v.notes}</span>}
              </div>
              <span style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                {new Date(v.created_at).toLocaleDateString()}
              </span>
            </div>
          ))}
        </div>

        {/* Reviews */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>
            Reviews ({reviews.length})
          </h2>
          <button onClick={() => setShowNewReview(true)} style={{
            cursor: 'pointer', padding: '5px 12px',
            background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.3)',
            borderRadius: 6, color: '#6366f1', fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
          }}>+ ADD</button>
        </div>

        {showNewReview && (
          <div style={{ background: 'var(--surface-card)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 10, padding: 16, marginBottom: 12 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 8 }}>
              <div>
                <label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>REVIEWER</label>
                <input value={reviewerName} onChange={e => setReviewerName(e.target.value)} style={inputStyle} />
              </div>
              <div>
                <label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>DECISION</label>
                <select value={reviewDecision} onChange={e => setReviewDecision(e.target.value)} style={inputStyle}>
                  <option value="">—</option>
                  <option value="accept">Accept</option>
                  <option value="minor_revision">Minor Revision</option>
                  <option value="major_revision">Major Revision</option>
                  <option value="reject">Reject</option>
                </select>
              </div>
            </div>
            <textarea value={reviewComments} onChange={e => setReviewComments(e.target.value)} placeholder="Review comments…" rows={3}
              style={{ ...inputStyle, marginBottom: 8, resize: 'vertical' }} />
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => reviewMutation.mutate()} style={{ padding: '6px 16px', cursor: 'pointer', background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.28)', borderRadius: 6, color: '#6366f1', fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>ADD REVIEW</button>
              <button onClick={() => setShowNewReview(false)} style={{ padding: '6px 12px', cursor: 'pointer', background: 'transparent', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-muted)', fontSize: 16 }}>CANCEL</button>
            </div>
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {reviews.map(r => (
            <div key={r.id} style={{
              background: 'var(--surface-card)', border: '1px solid var(--border)',
              borderRadius: 8, padding: '14px 16px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', fontSize: 17 }}>Round {r.round}</span>
                  {r.reviewer_name && <span style={{ color: 'var(--text-dim)' }}>— {r.reviewer_name}</span>}
                </div>
                {r.decision && (
                  <span style={{
                    fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)',
                    color: STATUS_COLORS[r.decision === 'accept' ? 'accepted' : r.decision === 'reject' ? 'rejected' : 'reviewing'],
                    padding: '1px 6px', borderRadius: 3, background: 'var(--surface-input)',
                  }}>{r.decision.replace('_', ' ').toUpperCase()}</span>
                )}
              </div>
              {r.comments && <p style={{ margin: 0, fontSize: 18, color: 'var(--text-2)', lineHeight: 1.5 }}>{r.comments}</p>}
              <div style={{ fontSize: 14, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 6 }}>
                {new Date(r.created_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
