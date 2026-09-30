import React, { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Admission } from '../api'
import { useAuth } from '../auth'

const STATUS_FILTERS: { key: string; label: string; accent: string }[] = [
  { key: '',         label: 'All',         accent: '#64748b' },
  { key: 'submitted', label: 'Submitted',  accent: '#6366f1' },
  { key: 'reviewing', label: 'Reviewing',  accent: '#f59e0b' },
  { key: 'accepted',  label: 'Accepted',   accent: '#10b981' },
  { key: 'rejected',  label: 'Rejected',   accent: '#f43f5e' },
]

const STATUS_BADGE: Record<string, { label: string; color: string; bg: string }> = {
  submitted: { label: 'Submitted', color: '#818cf8', bg: 'rgba(99,102,241,0.1)' },
  reviewing: { label: 'Reviewing', color: '#fbbf24', bg: 'rgba(245,158,11,0.1)' },
  accepted:  { label: 'Accepted',  color: '#34d399', bg: 'rgba(16,185,129,0.1)' },
  rejected:  { label: 'Rejected',  color: '#fb7185', bg: 'rgba(244,63,94,0.1)' },
}

export function AdmissionsPage() {
  const { isAdmin } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [statusFilter, setStatusFilter] = useState('')
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<{ imported: number; skipped: number } | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Admission | null>(null)
  const [deleting, setDeleting] = useState(false)

  const { data: admissions = [], isLoading, error } = useQuery({
    queryKey: ['admissions', statusFilter],
    queryFn: () => api.listAdmissions(statusFilter || undefined),
    refetchInterval: 20_000,
  })

  const importMutation = useMutation({
    mutationFn: (file: File) => api.importAdmissions(file),
    onSuccess: (data) => {
      setImportResult({ imported: data.imported, skipped: data.skipped })
      queryClient.invalidateQueries({ queryKey: ['admissions'] })
    },
    onSettled: () => setImporting(false),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteAdmission(id),
    onSuccess: () => {
      setDeleteTarget(null)
      queryClient.invalidateQueries({ queryKey: ['admissions'] })
    },
    onSettled: () => setDeleting(false),
  })

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setImporting(true)
    setImportResult(null)
    importMutation.mutate(file)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const pillBase: React.CSSProperties = {
    cursor: 'pointer', padding: '5px 14px',
    border: '1px solid var(--border)', borderRadius: 20,
    fontSize: 16, fontFamily: 'var(--font-mono)', fontWeight: 500,
    letterSpacing: '0.04em', transition: 'all 0.15s',
    background: 'transparent', color: 'var(--text-muted)',
  }

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
          <h1 className="page-title" style={{ fontSize: 18 }}>Admissions</h1>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {importResult && (
            <div style={{
              fontSize: 16, fontFamily: 'var(--font-mono)',
              color: '#34d399', background: 'rgba(16,185,129,0.08)',
              border: '1px solid rgba(16,185,129,0.2)',
              borderRadius: 6, padding: '4px 12px',
            }}>
              +{importResult.imported} imported{importResult.skipped > 0 ? `, ${importResult.skipped} skipped` : ''}
            </div>
          )}
          {isAdmin && (
            <>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={importing}
                style={{
                  cursor: importing ? 'default' : 'pointer',
                  padding: '7px 16px',
                  background: importing ? 'rgba(129,140,248,0.06)' : 'rgba(129,140,248,0.1)',
                  border: '1px solid rgba(129,140,248,0.3)',
                  borderRadius: 7, color: '#818cf8',
                  fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
                  letterSpacing: '0.04em', transition: 'background 0.14s',
                }}
                onMouseEnter={e => { if (!importing) e.currentTarget.style.background = 'rgba(129,140,248,0.22)' }}
                onMouseLeave={e => { e.currentTarget.style.background = importing ? 'rgba(129,140,248,0.06)' : 'rgba(129,140,248,0.1)' }}
              >{importing ? 'IMPORTING…' : '+ IMPORT EXCEL'}</button>
            </>
          )}
        </div>
      </div>

      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 28px' }}>

        {/* Status filter pills */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 24, flexWrap: 'wrap' }}>
          {STATUS_FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => setStatusFilter(f.key)}
              style={{
                ...pillBase,
                ...(statusFilter === f.key ? {
                  background: `${f.accent}22`,
                  borderColor: `${f.accent}44`,
                  color: f.accent,
                } : {}),
              }}
              onMouseEnter={e => {
                if (statusFilter !== f.key) {
                  e.currentTarget.style.borderColor = `${f.accent}44`
                  e.currentTarget.style.color = f.accent
                }
              }}
              onMouseLeave={e => {
                if (statusFilter !== f.key) {
                  e.currentTarget.style.borderColor = 'var(--border)'
                  e.currentTarget.style.color = 'var(--text-muted)'
                }
              }}
            >{f.label}</button>
          ))}
        </div>

        {/* Content */}
        {isLoading ? (
          <div style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 16, padding: '40px 0', textAlign: 'center' }}>
            Loading…
          </div>
        ) : error ? (
          <div style={{ color: '#f43f5e', fontFamily: 'var(--font-mono)', fontSize: 16 }}>{(error as Error).message}</div>
        ) : (
          <>
            <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', marginBottom: 10 }}>
              {admissions.length} admission{admissions.length !== 1 ? 's' : ''}
            </div>

            {admissions.length === 0 ? (
              <div style={{
                textAlign: 'center', padding: '60px 0',
                color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 16,
              }}>
                {statusFilter ? 'No admissions match this filter.' : 'No admissions yet. Import an Excel file to get started.'}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {admissions.map(a => {
                  const badge = STATUS_BADGE[a.status] ?? STATUS_BADGE.submitted
                  return (
                    <div
                      key={a.id}
                      onClick={() => navigate(`/admissions/${a.id}`)}
                      style={{
                        background: 'var(--surface-card)',
                        border: '1px solid var(--border)',
                        borderRadius: 10, padding: '16px 20px',
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        cursor: 'pointer', transition: 'border-color 0.15s',
                      }}
                      onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(129,140,248,0.3)' }}
                      onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border)' }}
                    >
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                          <span style={{ fontSize: 17, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {a.applicant_name}
                          </span>
                          <span style={{
                            fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 600,
                            color: badge.color, background: badge.bg,
                            border: `1px solid ${badge.color}33`,
                            borderRadius: 4, padding: '2px 8px', letterSpacing: '0.04em',
                            flexShrink: 0,
                          }}>{badge.label}</span>
                          {a.aid_percentage !== null && a.aid_percentage !== undefined && (
                            <span style={{
                              fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 600,
                              color: '#fbbf24', background: 'rgba(245,158,11,0.1)',
                              border: '1px solid rgba(245,158,11,0.25)',
                              borderRadius: 4, padding: '2px 8px', letterSpacing: '0.04em',
                              flexShrink: 0,
                            }}>{a.aid_percentage}% AID</span>
                          )}
                        </div>
                        <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                          {a.university && <span>{a.university}</span>}
                          {a.department && <span>{a.department}</span>}
                          {a.supervisor && <span style={{ color: 'var(--text-2)' }}>{a.supervisor}</span>}
                        </div>
                        <div style={{ fontSize: 16, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                          {a.service_areas.split(';').filter(Boolean).slice(0, 3).map((s, i) => (
                            <span key={i} style={{
                              marginRight: 8,
                              background: 'var(--surface-input)',
                              padding: '1px 6px', borderRadius: 3,
                            }}>{s.trim()}</span>
                          ))}
                          {a.service_areas.split(';').filter(Boolean).length > 3 && (
                            <span style={{ color: 'var(--text-3)' }}>+more</span>
                          )}
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0, marginLeft: 16 }}>
                        <div style={{ fontSize: 14, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', textAlign: 'right', lineHeight: 1.4 }}>
                          <div>{new Date(a.created_at).toLocaleDateString()}</div>
                        </div>
                        <span style={{ color: 'var(--text-dim)', fontSize: 16 }}>→</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
