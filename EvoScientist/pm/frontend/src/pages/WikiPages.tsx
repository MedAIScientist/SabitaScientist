import React, { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'

export function WikiPages() {
  const { id: labId } = useParams<{ id: string }>(); const navigate = useNavigate(); const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false); const [title, setTitle] = useState(''); const [content, setContent] = useState('')
  const { data: pages = [] } = useQuery({ queryKey: ['wiki', labId], queryFn: () => api.listWikiPages(labId!), enabled: Boolean(labId) })
  const create = useMutation({ mutationFn: () => api.createWikiPage(labId!, { title, content }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['wiki', labId] }); setShowForm(false); setTitle(''); setContent('') } })
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', padding: '32px 28px', maxWidth: 760, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 30, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>Lab Wiki</h1>
        <button onClick={() => setShowForm(f => !f)} style={{ cursor: 'pointer', padding: '7px 16px', background: 'rgba(255,128,21,0.1)', border: '1px solid rgba(255,128,21,0.3)', borderRadius: 7, color: '#ff8015', fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>+ NEW PAGE</button>
      </div>
      {showForm && (
        <form onSubmit={e => { e.preventDefault(); create.mutate() }} style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16, background: 'var(--surface-card)', border: '1px solid rgba(255,128,21,0.2)', borderRadius: 10, padding: 20 }}>
          <input value={title} onChange={e => setTitle(e.target.value)} required placeholder="Page title" style={{ padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 22, outline: 'none' }} />
          <textarea value={content} onChange={e => setContent(e.target.value)} placeholder="Markdown content..." rows={6} style={{ padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 18, outline: 'none', resize: 'vertical', fontFamily: 'var(--font-mono)' }} />
          <button type="submit" style={{ cursor: 'pointer', padding: '9px 0', background: '#ff8015', color: '#06091a', border: 'none', borderRadius: 7, fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>CREATE</button>
        </form>
      )}
      {pages.map(p => (
        <div key={p.id} onClick={() => navigate(`/labs/${labId}/wiki/${p.slug}`)} style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 18px', marginBottom: 6, cursor: 'pointer' }}>
          <div style={{ fontSize: 20, fontWeight: 500, color: 'var(--text-heading)' }}>{p.title}</div>
          <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>{p.tags?.join(', ') || ''}{p.updated_at ? ` · updated ${new Date(p.updated_at).toLocaleDateString()}` : ''}</div>
        </div>
      ))}
    </div>
  )
}
