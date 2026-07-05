import React, { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'

const STATUS_OPTS = ['draft', 'submitted', 'under_review', 'awarded', 'rejected', 'active', 'closed']

export function GrantDetail() {
  const { id } = useParams<{ id: string }>(); const navigate = useNavigate(); const qc = useQueryClient()
  const [editing, setEditing] = useState(false); const [status, setStatus] = useState('')
  const { data: grant } = useQuery({ queryKey: ['grant', id], queryFn: () => api.getGrant(id!), enabled: Boolean(id) })
  const update = useMutation({ mutationFn: (data: Record<string, unknown>) => api.updateGrant(id!, data), onSuccess: () => { qc.invalidateQueries({ queryKey: ['grant', id] }); setEditing(false) } })

  if (!grant) return <div style={{ padding: 40, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>LOADING…</div>
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', padding: '32px 28px', maxWidth: 700, margin: '0 auto' }}>
      <button onClick={() => navigate('/grants')} style={{ cursor: 'pointer', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-muted)', padding: '3px 9px', fontSize: 22, marginBottom: 16 }}>←</button>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
        <div><h1 style={{ margin: 0, fontSize: 28, fontWeight: 600, color: 'var(--text-heading)' }}>{grant.title}</h1>
          <div style={{ fontSize: 18, color: 'var(--text-dim)', marginTop: 4 }}>{grant.funder}</div></div>
        <button onClick={() => { if (!editing) { setStatus(grant.status) }; setEditing(e => !e) }} style={{ cursor: 'pointer', padding: '7px 14px', background: 'rgba(255,128,21,0.1)', border: '1px solid rgba(255,128,21,0.3)', borderRadius: 7, color: '#ff8015', fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{editing ? 'DONE' : 'EDIT'}</button>
      </div>
      {editing && (
        <div style={{ background: 'var(--surface-card)', border: '1px solid rgba(255,128,21,0.2)', borderRadius: 10, padding: 20, marginBottom: 20 }}>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
            {STATUS_OPTS.map(s => (
              <button key={s} onClick={() => update.mutate({ status: s })} style={{ cursor: 'pointer', padding: '3px 8px', fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 700, background: status === s ? 'rgba(99,102,241,0.15)' : 'transparent', border: `1px solid rgba(99,102,241,0.3)`, borderRadius: 3, color: '#6366f1' }}>{s.toUpperCase()}</button>
            ))}
          </div>
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <InfoRow label="Status" value={grant.status} />
        <InfoRow label="Amount" value={grant.amount_awarded ? `${grant.amount_awarded} ${grant.currency}` : '—'} />
        <InfoRow label="Submitted" value={grant.submitted_at?.slice(0, 10) || '—'} />
        <InfoRow label="Start" value={grant.start_date?.slice(0, 10) || '—'} />
        <InfoRow label="End" value={grant.end_date?.slice(0, 10) || '—'} />
      </div>
    </div>
  )
}
function InfoRow({ label, value }: { label: string; value: string }) {
  return <div><div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>{label}</div><div style={{ fontSize: 18, color: 'var(--text-2)', marginTop: 2 }}>{value}</div></div>
}
