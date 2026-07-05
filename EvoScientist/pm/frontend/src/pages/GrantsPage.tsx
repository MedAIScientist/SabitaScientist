import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Grant_ } from '../api'

const STATUS_COLORS: Record<string, string> = {
  draft: '#6b7280', submitted: '#6366f1', under_review: '#f59e0b',
  awarded: '#10b981', rejected: '#f43f5e', active: '#22c55e', closed: '#6b7280',
}

export function GrantsPage() {
  const navigate = useNavigate(); const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false); const [title, setTitle] = useState(''); const [funder, setFunder] = useState('')
  const { data: grants = [] } = useQuery({ queryKey: ['grants'], queryFn: () => api.listGrants() })
  const create = useMutation({ mutationFn: () => api.createGrant({ title, funder }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['grants'] }); setShowForm(false); setTitle(''); setFunder('') } })
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <div style={{ maxWidth: 760, margin: '0 auto', padding: '32px 28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <div><h1 style={{ margin: 0, fontSize: 30, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>Grants</h1>
            <p style={{ margin: '4px 0 0', fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>{grants.length} GRANTS</p></div>
          <button onClick={() => setShowForm(f => !f)} style={{ cursor: 'pointer', padding: '7px 16px', background: 'rgba(255,128,21,0.1)', border: '1px solid rgba(255,128,21,0.3)', borderRadius: 7, color: '#ff8015', fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>+ NEW</button>
        </div>
        {showForm && (
          <form onSubmit={e => { e.preventDefault(); create.mutate() }} style={{ background: 'var(--surface-card)', border: '1px solid rgba(255,128,21,0.2)', borderRadius: 10, padding: 24, marginBottom: 24 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
              <div><label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>TITLE</label><input value={title} onChange={e => setTitle(e.target.value)} required placeholder="Project title" style={{ padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 22, outline: 'none', width: '100%' }} /></div>
              <div><label style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>FUNDER</label><input value={funder} onChange={e => setFunder(e.target.value)} required placeholder="TÜBİTAK, TÜSEB, etc." style={{ padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 22, outline: 'none', width: '100%' }} /></div>
            </div>
            <button type="submit" style={{ padding: '9px 24px', cursor: 'pointer', background: '#ff8015', color: '#06091a', border: 'none', borderRadius: 7, fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>CREATE</button>
          </form>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {grants.map(g => (
            <div key={g.id} onClick={() => navigate(`/grants/${g.id}`)} style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 20px', cursor: 'pointer' }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(255,128,21,0.2)' }} onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div><div style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-heading)' }}>{g.title}</div>
                  <div style={{ fontSize: 17, color: 'var(--text-2)', marginTop: 2 }}>{g.funder}{g.amount_awarded ? ` · ${g.amount_awarded} ${g.currency}` : ''}</div>
                  <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>{g.created_at?.slice(0, 10)}</div></div>
                <span style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)', color: STATUS_COLORS[g.status] || '#6b7280', background: `${STATUS_COLORS[g.status] || '#6b7280'}14`, border: `1px solid ${STATUS_COLORS[g.status] || '#6b7280'}30`, borderRadius: 4, padding: '2px 8px' }}>{g.status.toUpperCase()}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
