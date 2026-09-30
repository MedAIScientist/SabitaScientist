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
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', padding: '32px 28px', maxWidth: 1100, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>Lab Wiki</h1>
        <button onClick={() => setShowForm(f => !f)} className="btn btn-primary">+ New page</button>
      </div>
      {showForm && (
        <form onSubmit={e => { e.preventDefault(); create.mutate() }} style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16, background: 'var(--surface-card)', border: '1px solid rgba(var(--accent-rgb),0.2)', borderRadius: 10, padding: 20 }}>
          <input value={title} onChange={e => setTitle(e.target.value)} required placeholder="Page title" style={{ padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 17, outline: 'none' }} />
          <textarea value={content} onChange={e => setContent(e.target.value)} placeholder="Markdown content..." rows={6} style={{ padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 15, outline: 'none', resize: 'vertical', fontFamily: 'var(--font-mono)' }} />
          <button type="submit" style={{ cursor: 'pointer', padding: '9px 0', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 7, fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>Create</button>
        </form>
      )}
      {pages.map(p => (
        <div key={p.id} onClick={() => navigate(`/labs/${labId}/wiki/${p.slug}`)} style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 18px', marginBottom: 6, cursor: 'pointer' }}>
          <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-heading)' }}>{p.title}</div>
          <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>{p.tags?.join(', ') || ''}{p.updated_at ? ` · updated ${new Date(p.updated_at).toLocaleDateString()}` : ''}</div>
        </div>
      ))}
    </div>
  )
}
