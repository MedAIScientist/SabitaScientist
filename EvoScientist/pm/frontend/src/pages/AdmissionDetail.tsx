import React, { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Admission } from '../api'
import { useAuth } from '../auth'

const STATUS_BADGE: Record<string, { label: string; color: string; bg: string }> = {
  submitted: { label: 'SUBMITTED', color: '#818cf8', bg: 'rgba(99,102,241,0.1)' },
  reviewing: { label: 'REVIEWING', color: '#fbbf24', bg: 'rgba(245,158,11,0.1)' },
  accepted:  { label: 'ACCEPTED',  color: '#34d399', bg: 'rgba(16,185,129,0.1)' },
  rejected:  { label: 'REJECTED',  color: '#fb7185', bg: 'rgba(244,63,94,0.1)' },
}

const labelStyle: React.CSSProperties = {
  fontSize: 15, fontWeight: 700, color: 'var(--text-dim)',
  letterSpacing: '0.1em', fontFamily: 'var(--font-mono)',
  marginBottom: 4,
}

const valueStyle: React.CSSProperties = {
  fontSize: 20, color: 'var(--text-heading)',
  fontFamily: 'var(--font-mono)', lineHeight: 1.5,
}

const sectionStyle: React.CSSProperties = {
  background: 'var(--surface-card)',
  border: '1px solid var(--border)',
  borderRadius: 10, padding: '24px',
  marginBottom: 16,
}

export function AdmissionDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { isAdmin } = useAuth()

  const [reviewNotes, setReviewNotes] = useState('')
  const [rejectNotes, setRejectNotes] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const { data: admission, isLoading } = useQuery({
    queryKey: ['admission', id],
    queryFn: () => api.getAdmission(id!),
    enabled: Boolean(id),
  })

  const updateMutation = useMutation({
    mutationFn: (data: { reviewer_id?: string | null; review_notes?: string | null }) =>
      api.updateAdmission(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admission', id] })
      queryClient.invalidateQueries({ queryKey: ['admissions'] })
    },
  })

  const acceptMutation = useMutation({
    mutationFn: (notes?: string) => api.acceptAdmission(id!, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admission', id] })
      queryClient.invalidateQueries({ queryKey: ['admissions'] })
      setActionError(null)
    },
    onError: (err: Error) => setActionError(err.message),
    onSettled: () => setSubmitting(false),
  })

  const rejectMutation = useMutation({
    mutationFn: (notes: string) => api.rejectAdmission(id!, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admission', id] })
      queryClient.invalidateQueries({ queryKey: ['admissions'] })
      setActionError(null)
      setRejectNotes('')
    },
    onError: (err: Error) => setActionError(err.message),
    onSettled: () => setSubmitting(false),
  })

  const [aidPercent, setAidPercent] = useState<number>(0)
  const [aidNotes, setAidNotes] = useState('')
  const [aidSaving, setAidSaving] = useState(false)
  const aidSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (admission) {
      if (admission.aid_percentage !== null && admission.aid_percentage !== undefined) {
        setAidPercent(admission.aid_percentage)
      } else {
        setAidPercent(0)
      }
      if (admission.aid_notes) {
        setAidNotes(admission.aid_notes)
      }
    }
  }, [admission?.id, admission?.aid_percentage])

  if (isLoading) {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 19 }}>LOADING…</span>
      </div>
    )
  }

  if (!admission) {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: '#f43f5e', fontFamily: 'var(--font-mono)', fontSize: 19 }}>Admission not found.</span>
      </div>
    )
  }

  const badge = STATUS_BADGE[admission.status] ?? STATUS_BADGE.submitted
  const canReview = isAdmin

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>

      {/* Header */}
      <div style={{
        padding: '0 28px', height: 54,
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'var(--surface-header)', backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            onClick={() => navigate('/admissions')}
            style={{
              cursor: 'pointer', background: 'var(--surface-input)',
              border: '1px solid var(--border)', borderRadius: 6,
              color: 'var(--text-muted)', padding: '3px 9px', fontSize: 22, lineHeight: 1,
              transition: 'color 0.15s, border-color 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = '#ff8015'; e.currentTarget.style.borderColor = 'rgba(255,128,21,0.3)' }}
            onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.borderColor = 'var(--border)' }}
          >←</button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span style={{ color: '#818cf8', fontSize: 21, fontFamily: 'var(--font-mono)' }}>
              {admission.applicant_name}
            </span>
            <span style={{
              fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 600,
              color: badge.color, background: badge.bg,
              border: `1px solid ${badge.color}33`,
              borderRadius: 4, padding: '2px 8px', letterSpacing: '0.06em',
            }}>{badge.label}</span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          {admission.created_project_id && (
            <button
              onClick={() => navigate(`/projects/${admission.created_project_id}`)}
              style={{
                cursor: 'pointer', padding: '7px 16px',
                background: 'rgba(16,185,129,0.1)',
                border: '1px solid rgba(16,185,129,0.3)',
                borderRadius: 7, color: '#10b981',
                fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)',
                letterSpacing: '0.08em', transition: 'background 0.14s',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(16,185,129,0.2)' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'rgba(16,185,129,0.1)' }}
            >PROJECT →</button>
          )}
        </div>
      </div>

      <div style={{ maxWidth: 760, margin: '0 auto', padding: '32px 28px' }}>

        {/* Error */}
        {actionError && (
          <div style={{
            padding: '10px 14px', marginBottom: 16,
            background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.2)',
            borderRadius: 6, color: '#f43f5e', fontSize: 18, fontFamily: 'var(--font-mono)',
          }}>{actionError}</div>
        )}

        {/* Applicant info */}
        <div style={sectionStyle}>
          <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)', marginBottom: 20, letterSpacing: '0.04em' }}>
            APPLICANT INFORMATION
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div>
              <div style={labelStyle}>NAME</div>
              <div style={valueStyle}>{admission.applicant_name || '—'}</div>
            </div>
            <div>
              <div style={labelStyle}>EMAIL</div>
              <div style={{ ...valueStyle, color: '#818cf8' }}>{admission.email || '—'}</div>
            </div>
            <div>
              <div style={labelStyle}>PHONE</div>
              <div style={valueStyle}>{admission.phone || '—'}</div>
            </div>
            <div>
              <div style={labelStyle}>SUPERVISOR</div>
              <div style={valueStyle}>{admission.supervisor || '—'}</div>
            </div>
            <div>
              <div style={labelStyle}>UNIVERSITY</div>
              <div style={valueStyle}>{admission.university || '—'}</div>
            </div>
            <div>
              <div style={labelStyle}>DEPARTMENT</div>
              <div style={valueStyle}>{admission.department || '—'}</div>
            </div>
          </div>
        </div>

        {/* Service details */}
        <div style={sectionStyle}>
          <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)', marginBottom: 20, letterSpacing: '0.04em' }}>
            SERVICE REQUEST DETAILS
          </div>
          <div style={{ marginBottom: 16 }}>
            <div style={labelStyle}>AREAS REQUESTED</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {admission.service_areas.split(';').filter(Boolean).map((s, i) => (
                <span key={i} style={{
                  padding: '4px 12px', borderRadius: 6,
                  background: 'rgba(129,140,248,0.1)',
                  border: '1px solid rgba(129,140,248,0.25)',
                  color: '#a5b4fc', fontSize: 18, fontFamily: 'var(--font-mono)',
                }}>{s.trim()}</span>
              ))}
            </div>
          </div>
          {admission.modas_members && (
            <div style={{ marginBottom: 16 }}>
              <div style={labelStyle}>MODAS MEMBERS</div>
              <div style={valueStyle}>{admission.modas_members.split(';').filter(Boolean).join(', ')}</div>
            </div>
          )}
          {admission.grant_context && (
            <div style={{ marginBottom: 16 }}>
              <div style={labelStyle}>GRANT CONTEXT</div>
              <div style={valueStyle}>{admission.grant_context}</div>
            </div>
          )}
          {admission.comments && (
            <div>
              <div style={labelStyle}>COMMENTS</div>
              <div style={{
                ...valueStyle, whiteSpace: 'pre-wrap',
                background: 'var(--surface-input)',
                padding: '12px', borderRadius: 6,
                fontSize: 18, color: 'var(--text-2)',
              }}>{admission.comments}</div>
            </div>
          )}
        </div>

        {/* Review section */}
        <div style={{ ...sectionStyle, borderColor: badge.color + '33' }}>
          <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)', marginBottom: 20, letterSpacing: '0.04em' }}>
            REVIEW
          </div>

          {admission.status === 'submitted' && (
            <div style={{ marginBottom: 16 }}>
              <p style={{ color: 'var(--text-2)', fontSize: 18, marginBottom: 12 }}>
                This application has not been assigned a reviewer yet.
              </p>
            </div>
          )}

          {admission.reviewed_at && (
            <div style={{ marginBottom: 16 }}>
              <div style={labelStyle}>REVIEWED AT</div>
              <div style={valueStyle}>{new Date(admission.reviewed_at).toLocaleString()}</div>
            </div>
          )}

          {admission.review_notes && (
            <div style={{ marginBottom: 16 }}>
              <div style={labelStyle}>REVIEW NOTES</div>
              <div style={{
                ...valueStyle, whiteSpace: 'pre-wrap',
                background: 'var(--surface-input)',
                padding: '12px', borderRadius: 6,
                fontSize: 18, color: 'var(--text-2)',
              }}>{admission.review_notes}</div>
            </div>
          )}

          {/* Accept / Reject actions */}
          {(admission.status === 'submitted' || admission.status === 'reviewing') && canReview && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  onClick={() => {
                    setSubmitting(true)
                    setActionError(null)
                    acceptMutation.mutate(reviewNotes || undefined)
                  }}
                  disabled={submitting}
                  style={{
                    cursor: submitting ? 'default' : 'pointer',
                    padding: '10px 24px',
                    background: submitting ? 'rgba(16,185,129,0.06)' : 'rgba(16,185,129,0.1)',
                    border: '1px solid rgba(16,185,129,0.3)',
                    borderRadius: 7, color: '#10b981',
                    fontSize: 19, fontWeight: 700, fontFamily: 'var(--font-mono)',
                    letterSpacing: '0.08em', transition: 'background 0.14s',
                  }}
                  onMouseEnter={e => { if (!submitting) e.currentTarget.style.background = 'rgba(16,185,129,0.2)' }}
                  onMouseLeave={e => { e.currentTarget.style.background = submitting ? 'rgba(16,185,129,0.06)' : 'rgba(16,185,129,0.1)' }}
                >{submitting ? 'PROCESSING…' : '✓ ACCEPT & CREATE PROJECT'}</button>
                <button
                  onClick={() => {
                    if (!rejectNotes.trim()) {
                      setActionError('Rejection requires notes explaining the reason.')
                      return
                    }
                    setSubmitting(true)
                    setActionError(null)
                    rejectMutation.mutate(rejectNotes)
                  }}
                  disabled={submitting}
                  style={{
                    cursor: submitting ? 'default' : 'pointer',
                    padding: '10px 24px',
                    background: submitting ? 'rgba(244,63,94,0.06)' : 'rgba(244,63,94,0.1)',
                    border: '1px solid rgba(244,63,94,0.3)',
                    borderRadius: 7, color: '#f43f5e',
                    fontSize: 19, fontWeight: 700, fontFamily: 'var(--font-mono)',
                    letterSpacing: '0.08em', transition: 'background 0.14s',
                  }}
                  onMouseEnter={e => { if (!submitting) e.currentTarget.style.background = 'rgba(244,63,94,0.2)' }}
                  onMouseLeave={e => { e.currentTarget.style.background = submitting ? 'rgba(244,63,94,0.06)' : 'rgba(244,63,94,0.1)' }}
                >✕ REJECT</button>
              </div>

              <div>
                <div style={{ ...labelStyle, marginBottom: 6 }}>REVIEW NOTES (optional for accept)</div>
                <textarea
                  value={reviewNotes}
                  onChange={e => setReviewNotes(e.target.value)}
                  placeholder="Review notes…"
                  rows={2}
                  style={{
                    width: '100%', padding: '10px 12px',
                    background: 'var(--surface-input)',
                    border: '1px solid var(--border)',
                    borderRadius: 7, color: 'var(--text)',
                    fontSize: 19, fontFamily: 'var(--font-mono)',
                    outline: 'none', resize: 'vertical',
                    marginBottom: 8,
                  }}
                  onFocus={e => { e.currentTarget.style.borderColor = 'rgba(129,140,248,0.35)' }}
                  onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
                />
              </div>

              <div>
                <div style={{ ...labelStyle, marginBottom: 6, color: '#f43f5e' }}>REJECTION REASON *</div>
                <textarea
                  value={rejectNotes}
                  onChange={e => setRejectNotes(e.target.value)}
                  placeholder="Required when rejecting…"
                  rows={2}
                  style={{
                    width: '100%', padding: '10px 12px',
                    background: 'var(--surface-input)',
                    border: '1px solid rgba(244,63,94,0.2)',
                    borderRadius: 7, color: 'var(--text)',
                    fontSize: 19, fontFamily: 'var(--font-mono)',
                    outline: 'none', resize: 'vertical',
                  }}
                  onFocus={e => { e.currentTarget.style.borderColor = 'rgba(244,63,94,0.4)' }}
                  onBlur={e => { e.currentTarget.style.borderColor = 'rgba(244,63,94,0.2)' }}
                />
              </div>
            </div>
          )}

          {!canReview && (admission.status === 'submitted' || admission.status === 'reviewing') && (
            <p style={{ color: 'var(--text-dim)', fontSize: 18 }}>You are not the assigned reviewer for this application.</p>
          )}

          {admission.status === 'accepted' && admission.created_project_id && (
            <div style={{
              padding: '14px 18px', background: 'rgba(16,185,129,0.06)',
              border: '1px solid rgba(16,185,129,0.18)', borderRadius: 8,
              fontSize: 18, color: '#34d399', fontFamily: 'var(--font-mono)',
            }}>
              Project created.{' '}
              <span
                onClick={() => navigate(`/projects/${admission.created_project_id}`)}
                style={{ cursor: 'pointer', textDecoration: 'underline', fontWeight: 600 }}
              >Open project →</span>
            </div>
          )}
        </div>

        {/* Financial Aid */}
        {admission.status === 'accepted' && (
          <div style={{ ...sectionStyle, borderColor: 'rgba(245,158,11,0.3)' }}>
            <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)', marginBottom: 20, letterSpacing: '0.04em' }}>
              FINANCIAL AID
              {aidSaving && <span style={{ fontSize: 14, color: 'var(--text-3)', marginLeft: 10, fontWeight: 400 }}>saving…</span>}
            </div>

            <div style={{ marginBottom: 18 }}>
              <div style={{ ...labelStyle, marginBottom: 10 }}>AID PERCENTAGE</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <input
                  type="range"
                  min={0} max={100} step={10}
                  value={aidPercent}
                  onChange={e => {
                    const v = Number(e.target.value)
                    setAidPercent(v)
                    if (aidSaveTimer.current) clearTimeout(aidSaveTimer.current)
                    setAidSaving(true)
                    aidSaveTimer.current = setTimeout(async () => {
                      try {
                        await api.grantAid(id!, { aid_percentage: v, notes: aidNotes || undefined })
                        queryClient.invalidateQueries({ queryKey: ['admission', id] })
                        queryClient.invalidateQueries({ queryKey: ['admissions'] })
                      } catch {
                        // silent — next interaction will retry
                      } finally {
                        setAidSaving(false)
                      }
                    }, 600)
                  }}
                  style={{ flex: 1, accentColor: '#f59e0b', height: 6 }}
                />
                <span style={{
                  minWidth: 60, textAlign: 'center',
                  fontSize: 24, fontWeight: 700, color: '#fbbf24',
                  fontFamily: 'var(--font-mono)',
                }}>{aidPercent}%</span>
              </div>
              <div style={{
                display: 'flex', justifyContent: 'space-between',
                marginTop: 6, padding: '0 2px',
              }}>
                {[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100].map(v => (
                  <button
                    key={v}
                    onClick={() => {
                      setAidPercent(v)
                      if (aidSaveTimer.current) clearTimeout(aidSaveTimer.current)
                      setAidSaving(true)
                      aidSaveTimer.current = setTimeout(async () => {
                        try {
                          await api.grantAid(id!, { aid_percentage: v, notes: aidNotes || undefined })
                          queryClient.invalidateQueries({ queryKey: ['admission', id] })
                          queryClient.invalidateQueries({ queryKey: ['admissions'] })
                        } catch {
                          // silent
                        } finally {
                          setAidSaving(false)
                        }
                      }, 600)
                    }}
                    style={{
                      cursor: 'pointer', fontSize: 12, fontFamily: 'var(--font-mono)',
                      color: aidPercent === v ? '#fbbf24' : 'var(--text-3)',
                      background: 'transparent', border: 'none',
                      padding: '2px 1px',
                      fontWeight: aidPercent === v ? 700 : 400,
                    }}
                  >{v}</button>
                ))}
              </div>
            </div>

            <div style={{ marginBottom: 18 }}>
              <div style={labelStyle}>NOTES</div>
              <textarea
                value={aidNotes}
                onChange={e => {
                  setAidNotes(e.target.value)
                }}
                onBlur={async e => {
                  e.currentTarget.style.borderColor = 'var(--border)'
                  try {
                    await api.grantAid(id!, { aid_percentage: aidPercent, notes: aidNotes || undefined })
                    queryClient.invalidateQueries({ queryKey: ['admission', id] })
                    queryClient.invalidateQueries({ queryKey: ['admissions'] })
                  } catch {
                    // silent
                  }
                }}
                placeholder="Financial aid details…"
                rows={2}
                style={{
                  width: '100%', padding: '10px 12px',
                  background: 'var(--surface-input)',
                  border: '1px solid var(--border)',
                  borderRadius: 7, color: 'var(--text)',
                  fontSize: 19, fontFamily: 'var(--font-mono)',
                  outline: 'none', resize: 'vertical',
                }}
                onFocus={e => { e.currentTarget.style.borderColor = 'rgba(245,158,11,0.4)' }}
              />
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
