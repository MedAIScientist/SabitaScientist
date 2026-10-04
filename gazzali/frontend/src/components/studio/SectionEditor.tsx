import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type ClaimItem, type Version } from '../../api'
import { NumberCheckBadge } from '../publication/NumberCheckBadge'
import { Panel } from './StudioPanels'

/** One section: its claims, its latest text, AI drafting and the author's own revision. */
export function SectionEditor({ pubId, section, claims, versions, onDraft, drafting, canDraft }: {
  pubId: string; section: string; claims: ClaimItem[]; versions: Version[]
  onDraft: () => void; drafting: boolean; canDraft: boolean
}) {
  const qc = useQueryClient()
  const withText = versions.filter(v => (v.content_length || 0) > 0)
  const [versionId, setVersionId] = useState<string | null>(null)
  const current = versionId ?? withText[0]?.id ?? null
  const { data: version, isLoading } = useQuery({
    queryKey: ['version-content', pubId, current], queryFn: () => api.getVersion(pubId, current!), enabled: !!current,
  })
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState('')
  useEffect(() => { setEditing(false); setVersionId(null) }, [section])
  useEffect(() => { if (version?.content != null) setText(version.content) }, [version?.content])
  const save = useMutation({
    mutationFn: () => api.saveSectionText(pubId, section, text),
    onSuccess: v => {
      setEditing(false)
      setVersionId(v.id)
      qc.invalidateQueries({ queryKey: ['pub-versions', pubId] })
      qc.invalidateQueries({ queryKey: ['paper-stages', pubId] })
    },
  })
  const isAi = (v?: Version) => (v?.generated_by ?? '').startsWith('ai')

  return (
    <Panel title={section[0].toUpperCase() + section.slice(1)} action={
      <div style={{ display: 'flex', gap: 6 }}>
        {!editing && version && <button className="btn" onClick={() => setEditing(true)}>Edit</button>}
        <button className={withText.length ? 'btn' : 'btn btn-primary'} disabled={drafting || !canDraft} onClick={onDraft}
          title={canDraft ? undefined : 'Generate the outline first'}>
          {drafting ? 'Drafting…' : withText.length ? 'Redraft with AI' : 'Draft with AI'}
        </button>
      </div>
    }>
      {claims.length > 0 ? (
        <details style={{ marginBottom: 8 }}>
          <summary style={{ cursor: 'pointer', fontSize: 13, color: 'var(--text-2)' }}>{claims.length} claim{claims.length > 1 ? 's' : ''} this section must support</summary>
          <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 13 }}>
            {claims.map(c => <li key={c.id}>{c.claim_text} <span style={{ color: 'var(--text-3)' }}>({c.evidence_ids.length} evidence)</span></li>)}
          </ul>
        </details>
      ) : <p style={{ fontSize: 13, color: 'var(--text-3)', margin: '0 0 8px' }}>No claims for this section yet; generate the outline first.</p>}

      {withText.length > 1 && !editing && (
        <select className="input" aria-label="Version" value={current ?? ''} onChange={e => setVersionId(e.target.value)} style={{ marginBottom: 8, maxWidth: 360 }}>
          {withText.map(v => <option key={v.id} value={v.id}>v{v.version} · {isAi(v) ? 'AI draft' : 'your edit'} · {new Date(v.created_at).toLocaleDateString()}</option>)}
        </select>
      )}

      {editing ? (
        <>
          <textarea className="input" aria-label={`${section} text`} rows={18} value={text} onChange={e => setText(e.target.value)}
            style={{ width: '100%', fontFamily: 'var(--font-body, inherit)', lineHeight: 1.55 }} />
          <div style={{ display: 'flex', gap: 6, marginTop: 6, alignItems: 'center' }}>
            <button className="btn btn-primary" disabled={save.isPending || !text.trim()} onClick={() => save.mutate()}>{save.isPending ? 'Saving…' : 'Save my revision'}</button>
            <button className="btn" onClick={() => { setEditing(false); setText(version?.content ?? '') }}>Cancel</button>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>Saved as your own version; the integrity check needs one.</span>
          </div>
          {save.isError && <div className="msg msg-error" role="alert">{(save.error as Error).message}</div>}
        </>
      ) : !current ? (
        <p style={{ color: 'var(--text-3)', margin: 0 }}>No text yet. Draft it with AI from the claims, or <button className="text-link" style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer' }} onClick={() => { setText(''); setEditing(true) }}>write it yourself</button>.</p>
      ) : isLoading ? <p>Loading…</p> : (
        <>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12, color: 'var(--text-3)', marginBottom: 6 }}>
            <span>{isAi(version) ? 'AI draft' : 'Your edit'} · v{version?.version}</span>
            <NumberCheckBadge check={version?.verification} />
          </div>
          <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6, fontSize: 15, maxHeight: 520, overflow: 'auto' }}>{version?.content}</div>
        </>
      )}
    </Panel>
  )
}
