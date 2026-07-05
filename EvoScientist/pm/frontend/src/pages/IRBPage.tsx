import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'

export function IRBPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false); const [title, setTitle] = useState(''); const [institution, setInstitution] = useState(''); const [protocolNumber, setProtocolNumber] = useState(''); const [projectId, setProjectId] = useState('')
  const { data: irbs = [] } = useQuery({ queryKey: ['irbs'], queryFn: () => api.listIrbs() })
  const create = useMutation({
    mutationFn: () => api.createIrb({ title, institution, protocol_number: protocolNumber, project_id: projectId || undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['irbs'] }); setShowForm(false); setTitle(''); setInstitution(''); setProtocolNumber(''); setProjectId('') }
  })
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', padding: '32px 28px', maxWidth: 760, margin: '0 auto' }}>
      <h1 style={{ margin: '0 0 24px', fontSize: 30, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>IRB / Ethics Approvals</h1>
      <button onClick={() => setShowForm(f => !f)} style={{ cursor: 'pointer', padding: '7px 16px', background: 'rgba(255,128,21,0.1)', border: '1px solid rgba(255,128,21,0.3)', borderRadius: 7, color: '#ff8015', fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', marginBottom: 16 }}>+ NEW</button>
      {showForm && (
        <form onSubmit={e => { e.preventDefault(); create.mutate() }} style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16, background: 'var(--surface-card)', border: '1px solid rgba(255,128,21,0.2)', borderRadius: 10, padding: 20 }}>
          <input value={title} onChange={e => setTitle(e.target.value)} required placeholder="Protocol title" style={{ padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 18, outline: 'none' }} />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
            <input value={institution} onChange={e => setInstitution(e.target.value)} required placeholder="Institution" style={{ padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 18, outline: 'none' }} />
            <input value={protocolNumber} onChange={e => setProtocolNumber(e.target.value)} required placeholder="Protocol #" style={{ padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 18, outline: 'none' }} />
            <input value={projectId} onChange={e => setProjectId(e.target.value)} placeholder="Project ID (opt)" style={{ padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 18, outline: 'none' }} />
          </div>
          <button type="submit" style={{ cursor: 'pointer', padding: '9px 0', background: '#ff8015', color: '#06091a', border: 'none', borderRadius: 7, fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>CREATE</button>
        </form>
      )}
      {irbs.map(i => (
        <div key={i.id} style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 18px', marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div><div style={{ fontSize: 20, fontWeight: 500, color: 'var(--text-heading)' }}>{i.title}</div>
              <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>{i.institution} · {i.protocol_number}{i.approval_date ? ` · Approved: ${i.approval_date}` : ''}</div></div>
            <span style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)', color: i.status === 'approved' ? '#10b981' : i.status === 'expired' ? '#f43f5e' : '#f59e0b', padding: '2px 7px', borderRadius: 3, background: 'var(--surface-input)' }}>{i.status.toUpperCase()}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
