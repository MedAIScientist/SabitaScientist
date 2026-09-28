import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'

export function MemoryPage() {
  const qc = useQueryClient()
  const [projectId, setProjectId] = useState('')
  const [searchQ, setSearchQ] = useState('')
  const [showRecord, setShowRecord] = useState(false)
  const [recTitle, setRecTitle] = useState('')
  const [recBody, setRecBody] = useState('')

  const obs = useQuery({
    queryKey: ['observations', projectId],
    queryFn: () => api.listObservations(projectId),
    enabled: !!projectId,
  })

  const search = useQuery({
    queryKey: ['observation-search', projectId, searchQ],
    queryFn: () => api.searchObservations(projectId, searchQ),
    enabled: !!projectId && searchQ.length >= 2,
  })

  const record = useMutation({
    mutationFn: () => api.recordObservation(projectId, recTitle, recBody || undefined),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['observations', projectId] }); setShowRecord(false); setRecTitle(''); setRecBody('') },
  })

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', padding: '32px 28px', maxWidth: 860, margin: '0 auto' }}>
      <h1 style={{ margin: '0 0 24px', fontSize: 30, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>Memory / Observations</h1>

      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <input value={projectId} onChange={e => setProjectId(e.target.value)} placeholder="Project ID" style={{ flex: 1, padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 18, outline: 'none', fontFamily: 'var(--font-mono)' }} />
        <button onClick={() => setShowRecord(f => !f)} style={{ cursor: 'pointer', padding: '7px 16px', background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.28)', borderRadius: 7, color: '#10b981', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>+ RECORD</button>
      </div>

      {showRecord && (
        <form onSubmit={e => { e.preventDefault(); record.mutate() }} style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: 16, marginBottom: 16 }}>
          <input value={recTitle} onChange={e => setRecTitle(e.target.value)} required placeholder="Title" style={{ width: '100%', padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 16, outline: 'none', boxSizing: 'border-box', marginBottom: 8 }} />
          <textarea value={recBody} onChange={e => setRecBody(e.target.value)} placeholder="Body (optional)" rows={4} style={{ width: '100%', padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 15, outline: 'none', boxSizing: 'border-box', fontFamily: 'var(--font-mono)', resize: 'vertical', marginBottom: 8 }} />
          <button type="submit" disabled={record.isPending} style={{ cursor: 'pointer', padding: '7px 16px', background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.28)', borderRadius: 7, color: '#10b981', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>SAVE</button>
        </form>
      )}

      {projectId && (
        <>
          <input value={searchQ} onChange={e => setSearchQ(e.target.value)} placeholder="Search observations..." style={{ width: '100%', padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 18, outline: 'none', boxSizing: 'border-box', marginBottom: 16, fontFamily: 'var(--font-mono)' }} />

          {searchQ.length >= 2 && search.data && search.data.results.length > 0 && (
            <>
              <h3 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-heading)', margin: '0 0 8px', fontFamily: 'var(--font-mono)' }}>Search Results</h3>
              {search.data.results.map(h => (
                <div key={h.id} style={{ background: 'var(--surface-card)', border: '1px solid rgba(99,102,241,0.3)', borderRadius: 10, padding: '12px 16px', marginBottom: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-heading)' }}>{h.title}</div>
                    <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>score: {h.score.toFixed(3)}</span>
                  </div>
                  <div style={{ fontSize: 14, color: 'var(--text-dim)', marginTop: 4, whiteSpace: 'pre-wrap' }}>{h.body.slice(0, 300)}</div>
                </div>
              ))}
            </>
          )}

          <h3 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-heading)', margin: '16px 0 8px', fontFamily: 'var(--font-mono)' }}>All Observations ({obs.data?.total ?? 0})</h3>
          {(obs.data?.observations ?? []).map(o => (
            <div key={o.id} style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px', marginBottom: 6 }}>
              <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-heading)' }}>{o.title}</div>
              <div style={{ fontSize: 14, color: 'var(--text-dim)', marginTop: 4, whiteSpace: 'pre-wrap' }}>{o.body.slice(0, 400)}</div>
              <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', padding: '2px 6px', background: 'var(--surface-input)', borderRadius: 3 }}>{o.memory_type}</span>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', padding: '2px 6px', background: 'var(--surface-input)', borderRadius: 3 }}>{o.scope}</span>
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  )
}
