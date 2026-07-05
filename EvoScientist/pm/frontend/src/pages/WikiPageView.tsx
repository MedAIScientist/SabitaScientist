import React, { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'

export function WikiPageView() {
  const { id: labId, slug } = useParams<{ id: string; slug: string }>(); const navigate = useNavigate(); const qc = useQueryClient()
  const [editing, setEditing] = useState(false); const [editContent, setEditContent] = useState(''); const [editTitle, setEditTitle] = useState('')
  const { data: pages = [] } = useQuery({ queryKey: ['wiki', labId], queryFn: () => api.listWikiPages(labId!), enabled: Boolean(labId) })
  const page = Array.isArray(pages) ? pages.find((p: any) => p.slug === slug) : null
  const update = useMutation({
    mutationFn: () => api.updateWikiPage(labId!, page!.id, { content: editContent, title: editTitle || undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['wiki', labId] }); setEditing(false) }
  })
  if (!page) return <div style={{ padding: 40, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>LOADING…</div>

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', padding: '32px 28px', maxWidth: 760, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
        {editing ? (
          <input value={editTitle} onChange={e => setEditTitle(e.target.value)} style={{ fontSize: 28, fontWeight: 600, padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', outline: 'none', width: '100%' }} />
        ) : (
          <h1 style={{ margin: 0, fontSize: 28, fontWeight: 600, color: 'var(--text-heading)' }}>{page.title}</h1>
        )}
        <button onClick={() => { if (!editing) { setEditContent(page.content || ''); setEditTitle(page.title) }; setEditing(e => !e) }} style={{ cursor: 'pointer', padding: '7px 14px', background: 'rgba(255,128,21,0.1)', border: '1px solid rgba(255,128,21,0.3)', borderRadius: 7, color: '#ff8015', fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', marginLeft: 12 }}>{editing ? 'CANCEL' : 'EDIT'}</button>
      </div>
      {editing ? (
        <div>
          <textarea value={editContent} onChange={e => setEditContent(e.target.value)} rows={15} style={{ width: '100%', padding: '12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 18, outline: 'none', fontFamily: 'var(--font-mono)', resize: 'vertical', boxSizing: 'border-box' }} />
          <button onClick={() => update.mutate()} style={{ marginTop: 10, padding: '9px 24px', cursor: 'pointer', background: '#ff8015', color: '#06091a', border: 'none', borderRadius: 7, fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>SAVE</button>
        </div>
      ) : (
        <pre style={{ fontSize: 18, color: 'var(--text-2)', lineHeight: 1.6, whiteSpace: 'pre-wrap', fontFamily: 'inherit', margin: 0 }}>{page.content || '(empty)'}</pre>
      )}
    </div>
  )
}
