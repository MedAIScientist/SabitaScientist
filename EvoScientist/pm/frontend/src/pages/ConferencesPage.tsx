import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'

export function ConferencesPage() {
  const navigate = useNavigate(); const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false); const [name, setName] = useState(''); const [deadline, setDeadline] = useState('')
  const { data: confs = [] } = useQuery({ queryKey: ['conferences'], queryFn: () => api.listConferences() })
  const create = useMutation({ mutationFn: () => api.createConference({ name, deadline: deadline || undefined }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['conferences'] }); setShowForm(false); setName(''); setDeadline('') } })
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', padding: '32px 28px', maxWidth: 760, margin: '0 auto' }}>
      <h1 style={{ margin: '0 0 24px', fontSize: 30, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>Conferences</h1>
      <button onClick={() => setShowForm(f => !f)} style={{ cursor: 'pointer', padding: '7px 16px', background: 'rgba(255,128,21,0.1)', border: '1px solid rgba(255,128,21,0.3)', borderRadius: 7, color: '#ff8015', fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', marginBottom: 16 }}>+ NEW</button>
      {showForm && (
        <form onSubmit={e => { e.preventDefault(); create.mutate() }} style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
          <input value={name} onChange={e => setName(e.target.value)} required placeholder="Conference name" style={{ flex: 1, padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 18, outline: 'none' }} />
          <input type="date" value={deadline} onChange={e => setDeadline(e.target.value)} style={{ padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 18, outline: 'none' }} />
          <button type="submit" style={{ cursor: 'pointer', background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.28)', borderRadius: 7, color: '#10b981', fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>CREATE</button>
        </form>
      )}
      {confs.map(c => (
        <div key={c.id} style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 18px', marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div><div style={{ fontSize: 20, fontWeight: 500, color: 'var(--text-heading)' }}>{c.name}</div>
              <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>{c.venue || ''} {c.deadline ? `· Deadline: ${c.deadline}` : ''}</div></div>
            <span style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)', color: ['accepted', 'presented'].includes(c.status) ? '#10b981' : c.status === 'rejected' ? '#f43f5e' : '#f59e0b', padding: '2px 7px', borderRadius: 3, background: 'var(--surface-input)' }}>{c.status.toUpperCase()}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
