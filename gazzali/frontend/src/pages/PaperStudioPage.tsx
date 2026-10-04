import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, paperApi, ClaimItem, IntegrityCheck } from '../api'

const SECTION_TABS = ['abstract', 'introduction', 'related work', 'methods', 'results', 'discussion', 'conclusion']
const STAGE_ORDER = [
  { key: 'setup', label: '1. Setup' },
  { key: 'evidence', label: '2. Evidence pack' },
  { key: 'outline', label: '3. Outline & claims' },
  { key: 'sections', label: '4. Section drafts' },
  { key: 'coherence', label: '5. Coherence' },
  { key: 'integrity', label: '6. Integrity' },
  { key: 'submit', label: '7. Submit pack' },
]

/**
 * Paper Studio — one workspace for the systematic paper pipeline.
 * Left: stage checklist. Center: section editor + AI for this section.
 * Right: evidence pack, claim map, integrity.
 */
export function PaperStudioPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [section, setSection] = useState('introduction')
  const [activeStage, setActiveStage] = useState<string>('evidence')
  const [notice, setNotice] = useState<string | null>(null)
  const [integrityResult, setIntegrityResult] = useState<{ passed: boolean; checks: IntegrityCheck[] } | null>(null)
  const [newPoint, setNewPoint] = useState({ comment: '', action: '', section: '' })
  const [openVersionId, setOpenVersionId] = useState<string | null>(null)

  const { data: pub, isLoading } = useQuery({
    queryKey: ['publication', id],
    queryFn: () => api.getPublication(id!),
    enabled: !!id,
  })
  const { data: stages } = useQuery({
    queryKey: ['paper-stages', id],
    queryFn: () => paperApi.stages(id!),
    enabled: !!id,
  })
  const { data: context } = useQuery({
    queryKey: ['paper-context', id],
    queryFn: () => paperApi.context(id!),
    enabled: !!id,
  })
  const { data: outline } = useQuery({
    queryKey: ['paper-outline', id],
    queryFn: () => paperApi.outline(id!),
    enabled: !!id,
  })
  const { data: versions } = useQuery({
    queryKey: ['pub-versions', id],
    queryFn: () => api.listVersions(id!),
    enabled: !!id,
  })

  // Newest stored text for the selected section (section tags or full-draft)
  const sectionVersions = (versions || []).filter(v =>
    (v.section || '').toLowerCase() === section.toLowerCase()
    || v.section === 'full-draft'
  )
  const activeVersionId = openVersionId
    || sectionVersions.find(v => (v.content_length || 0) > 0)?.id
    || null
  const { data: activeVersion, isLoading: loadingContent } = useQuery({
    queryKey: ['version-content', id, activeVersionId],
    queryFn: () => api.getVersion(id!, activeVersionId!),
    enabled: !!id && !!activeVersionId,
  })
  const { data: reviewPoints } = useQuery({
    queryKey: ['review-points', id],
    queryFn: () => paperApi.reviewPoints(id!),
    enabled: !!id,
  })

  const snap = useMutation({
    mutationFn: () => paperApi.snapshot(id!, 'Evidence pack'),
    onSuccess: () => {
      setNotice('Evidence pack snapshotted.')
      qc.invalidateQueries({ queryKey: ['paper-context', id] })
      qc.invalidateQueries({ queryKey: ['paper-stages', id] })
    },
    onError: (e: Error) => setNotice(e.message),
  })

  const genOutline = useMutation({
    mutationFn: () => paperApi.generateOutline(id!),
    onSuccess: (r) => {
      setNotice(`Outline generated — ${r.claims.length} claims bound to evidence.`)
      qc.invalidateQueries({ queryKey: ['paper-outline', id] })
      qc.invalidateQueries({ queryKey: ['paper-stages', id] })
    },
    onError: (e: Error) => setNotice(e.message),
  })

  const draftSec = useMutation({
    mutationFn: () => paperApi.draftSection(id!, section, 'academic'),
    onSuccess: (r) => {
      setNotice(`Drafting ${section}… (${r.claim_count} claims, ${r.evidence_ids.length} evidence ids)`)
      qc.invalidateQueries({ queryKey: ['pub-versions', id] })
      qc.invalidateQueries({ queryKey: ['paper-stages', id] })
    },
    onError: (e: Error) => setNotice(e.message),
  })

  const runIntegrity = useMutation({
    mutationFn: () => paperApi.integrity(id!),
    onSuccess: (r) => {
      setIntegrityResult(r)
      setNotice(r.passed ? 'Integrity checks passed.' : `Integrity failed: ${r.blocking.join(', ')}`)
      qc.invalidateQueries({ queryKey: ['paper-stages', id] })
    },
    onError: (e: Error) => setNotice(e.message),
  })

  const runCoherence = useMutation({
    mutationFn: () => paperApi.coherence(id!),
    onSuccess: () => {
      setNotice('Coherence pass started.')
      qc.invalidateQueries({ queryKey: ['paper-stages', id] })
    },
    onError: (e: Error) => setNotice(e.message),
  })

  const addPoint = useMutation({
    mutationFn: () => paperApi.addReviewPoint(id!, {
      comment: newPoint.comment,
      action: newPoint.action || undefined,
      section: newPoint.section || undefined,
    }),
    onSuccess: () => {
      setNewPoint({ comment: '', action: '', section: '' })
      qc.invalidateQueries({ queryKey: ['review-points', id] })
    },
    onError: (e: Error) => setNotice(e.message),
  })

  if (isLoading) return <div style={{ padding: 32, color: 'var(--text-2)' }}>Loading Paper Studio…</div>
  if (!pub) return <div style={{ padding: 32 }}>Publication not found.</div>

  const stageFlags = stages?.stages || {}
  const claims = outline?.claims || []
  const sectionClaims = claims.filter(c => c.section.toLowerCase() === section)

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 10,
        background: 'var(--surface-header)', borderBottom: '1px solid var(--border)',
        padding: '12px 24px', display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <button onClick={() => navigate('/publications')} style={ghostBtn}>← Papers</button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 style={{
            margin: 0, fontSize: 17, color: 'var(--text-heading)',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>{pub.title}</h1>
          <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 2 }}>
            Paper Studio · {pub.status} · {stages?.claim_count ?? 0} claims · {context?.summary.metric_count ?? 0} metrics in pack
          </div>
        </div>
        <button onClick={() => navigate(`/publications/${id}`)} style={ghostBtn}>Metadata</button>
      </div>

      {notice && (
        <div style={{
          margin: '12px 24px 0', padding: '10px 14px', borderRadius: 8,
          background: 'rgba(255,128,21,0.1)', border: '1px solid rgba(255,128,21,0.28)', fontSize: 13,
        }}>{notice}</div>
      )}

      <div style={{
        display: 'grid', gridTemplateColumns: '200px 1fr 320px', gap: 16,
        padding: '16px 24px 40px', maxWidth: 1360, margin: '0 auto',
      }}>
        {/* Stage rail */}
        <aside>
          <div style={label}>Pipeline</div>
          {STAGE_ORDER.map(s => {
            const done = !!stageFlags[s.key]
            return (
              <button
                key={s.key}
                onClick={() => setActiveStage(s.key)}
                style={{
                  display: 'flex', width: '100%', gap: 8, alignItems: 'center',
                  padding: '9px 10px', marginBottom: 4, borderRadius: 8, cursor: 'pointer',
                  background: activeStage === s.key ? 'rgba(255,128,21,0.12)' : 'transparent',
                  border: activeStage === s.key ? '1px solid rgba(255,128,21,0.35)' : '1px solid transparent',
                  color: 'var(--text)', fontSize: 13, textAlign: 'left',
                }}
              >
                <span style={{ color: done ? '#10b981' : 'var(--text-dim)' }}>{done ? '✓' : '○'}</span>
                <span>{s.label}</span>
              </button>
            )
          })}

          <div style={{ ...card, marginTop: 16 }}>
            <div style={label}>Actions</div>
            <button onClick={() => snap.mutate()} style={{ ...primaryBtn, width: '100%', marginBottom: 8 }}>
              {snap.isPending ? 'Saving…' : 'Snapshot evidence'}
            </button>
            <button onClick={() => genOutline.mutate()} style={{ ...primaryBtn, width: '100%', marginBottom: 8 }}>
              {genOutline.isPending ? 'Generating…' : 'Generate outline'}
            </button>
            <button onClick={() => draftSec.mutate()} style={{ ...primaryBtn, width: '100%', marginBottom: 8 }}>
              {draftSec.isPending ? 'Drafting…' : `Draft ${section}`}
            </button>
            <button onClick={() => runCoherence.mutate()} style={{ ...ghostBtn, width: '100%', marginBottom: 8 }}>
              Coherence pass
            </button>
            <button onClick={() => runIntegrity.mutate()} style={{ ...ghostBtn, width: '100%' }}>
              Run integrity
            </button>
          </div>
        </aside>

        {/* Center — section editor */}
        <main>
          <section style={card}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h2 style={h2}>Manuscript sections</h2>
              <span style={muted}>AI applies to the selected section only</span>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
              {SECTION_TABS.map(s => (
                <button
                  key={s}
                  onClick={() => setSection(s)}
                  style={{
                    ...chip,
                    background: section === s ? 'rgba(255,128,21,0.15)' : 'var(--surface-input)',
                    borderColor: section === s ? 'rgba(255,128,21,0.45)' : 'var(--border)',
                    color: section === s ? '#ff8015' : 'var(--text-2)',
                  }}
                >{s}</button>
              ))}
            </div>

            <div style={{ fontSize: 13, color: 'var(--text-2)', marginBottom: 8 }}>
              Outline claims for <strong>{section}</strong>
            </div>
            {sectionClaims.length === 0 ? (
              <div style={{ ...muted, padding: 12, border: '1px dashed var(--border)', borderRadius: 8, marginBottom: 12 }}>
                No claims yet — generate the outline (Stage 3). Claims bind prose to evidence ids.
              </div>
            ) : (
              sectionClaims.map(c => (
                <div key={c.id} style={{
                  padding: '10px 12px', borderRadius: 8, marginBottom: 8,
                  background: 'var(--surface-input)', border: '1px solid var(--border)',
                }}>
                  <div style={{ fontSize: 13 }}>{c.claim_text}</div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                    {c.evidence_ids.map(eid => (
                      <span key={eid} style={{ ...chip, fontSize: 10, padding: '2px 7px', cursor: 'default' }}>{eid}</span>
                    ))}
                    {!c.evidence_ids.length && <span style={{ fontSize: 11, color: '#f43f5e' }}>no evidence bound</span>}
                  </div>
                </div>
              ))
            )}

            <div style={{ marginTop: 12 }}>
              <button onClick={() => draftSec.mutate()} disabled={draftSec.isPending} style={primaryBtn}>
                {draftSec.isPending ? 'Drafting…' : `Draft “${section}” from claims + evidence`}
              </button>
            </div>
          </section>

          {/* Manuscript text for the selected section */}
          <section style={{ ...card, marginTop: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <h2 style={{ ...h2, marginBottom: 0 }}>Manuscript text — {section}</h2>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {sectionVersions.slice(0, 6).map(v => (
                  <button
                    key={v.id}
                    onClick={() => setOpenVersionId(v.id)}
                    style={{
                      ...chip,
                      cursor: 'pointer',
                      background: activeVersionId === v.id ? 'rgba(255,128,21,0.15)' : 'var(--surface-input)',
                      borderColor: activeVersionId === v.id ? 'rgba(255,128,21,0.45)' : 'var(--border)',
                      color: activeVersionId === v.id ? '#ff8015' : 'var(--text-2)',
                    }}
                    title={v.notes || ''}
                  >
                    {(v.generated_by || 'human').replace('ai-', '')} · {v.content_length || 0}ch
                  </button>
                ))}
              </div>
            </div>

            {loadingContent && <div style={muted}>Loading section text…</div>}
            {!loadingContent && !activeVersionId && (
              <div style={{
                padding: '28px 18px', borderRadius: 10, border: '1px dashed var(--border)',
                color: 'var(--text-2)', fontSize: 13, lineHeight: 1.6, textAlign: 'center',
              }}>
                No text yet for <strong>{section}</strong>.
                <div style={{ marginTop: 8 }}>
                  Use <strong>Draft “{section}”</strong> above to generate from claims + project evidence.
                </div>
              </div>
            )}
            {!loadingContent && activeVersionId && (
              <div
                style={{
                  whiteSpace: 'pre-wrap', fontFamily: 'var(--font-mono)', fontSize: 13.5,
                  lineHeight: 1.65, color: 'var(--text)', padding: '16px 18px',
                  background: 'var(--surface-input)', borderRadius: 10,
                  border: '1px solid var(--border)', maxHeight: 520, overflowY: 'auto',
                }}
              >
                {activeVersion?.content || '(this version has no stored text)'}
              </div>
            )}
            {activeVersion?.notes && (
              <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 8 }}>
                {activeVersion.notes}
                {activeVersion.generated_by ? ` · ${activeVersion.generated_by}` : ''}
              </div>
            )}
          </section>

          <section style={{ ...card, marginTop: 14 }}>
            <h2 style={h2}>Draft history</h2>
            {(versions || []).slice(0, 10).map(v => (
              <div key={v.id} style={{
                display: 'flex', gap: 10, alignItems: 'center', padding: '8px 0',
                borderBottom: '1px solid var(--border)', fontSize: 13,
              }}>
                <span style={{
                  fontSize: 10, fontFamily: 'var(--font-mono)', padding: '2px 8px', borderRadius: 999,
                  background: (v.generated_by || '').startsWith('ai') ? 'rgba(255,128,21,0.12)' : 'var(--surface-input)',
                  color: (v.generated_by || '').startsWith('ai') ? '#ff8015' : 'var(--text-2)',
                  border: '1px solid var(--border)',
                }}>{v.generated_by || 'human'}</span>
                <span style={{ flex: 1 }}>{v.notes || v.section || 'version'}</span>
                <span style={muted}>{(v.created_at || '').slice(0, 16).replace('T', ' ')}</span>
              </div>
            ))}
            {!versions?.length && <div style={muted}>No versions yet.</div>}
          </section>

          <section style={{ ...card, marginTop: 14 }}>
            <h2 style={h2}>Reviewer points</h2>
            {(reviewPoints?.points || []).map(p => (
              <div key={p.id} style={{
                display: 'flex', gap: 10, padding: '8px 10px', borderRadius: 8, marginBottom: 6,
                background: 'var(--surface-input)', border: '1px solid var(--border)', fontSize: 13,
              }}>
                <span style={{ ...chip, fontSize: 10 }}>{p.status}</span>
                <div style={{ flex: 1 }}>
                  <div>{p.comment}</div>
                  {p.action && <div style={{ fontSize: 11, color: 'var(--text-2)', marginTop: 2 }}>→ {p.action}</div>}
                </div>
              </div>
            ))}
            <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
              <input
                placeholder="Reviewer comment"
                value={newPoint.comment}
                onChange={e => setNewPoint(p => ({ ...p, comment: e.target.value }))}
                style={input}
              />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 120px', gap: 8 }}>
                <input placeholder="Action" value={newPoint.action} onChange={e => setNewPoint(p => ({ ...p, action: e.target.value }))} style={input} />
                <input placeholder="Section" value={newPoint.section} onChange={e => setNewPoint(p => ({ ...p, section: e.target.value }))} style={input} />
                <button
                  onClick={() => addPoint.mutate()}
                  disabled={!newPoint.comment.trim() || addPoint.isPending}
                  style={primaryBtn}
                >Add</button>
              </div>
            </div>
          </section>
        </main>

        {/* Right rail */}
        <aside>
          <section style={card}>
            <h2 style={h2}>Evidence pack</h2>
            {context ? (
              <>
                {context.summary.warnings.map(w => (
                  <div key={w} style={{
                    fontSize: 11, color: '#f59e0b', marginBottom: 6, padding: '6px 8px',
                    background: 'rgba(245,158,11,0.08)', borderRadius: 6,
                  }}>⚠ {w}</div>
                ))}
                {Object.entries(context.sources).map(([kind, rows]) => (
                  rows.length === 0 ? null : (
                    <div key={kind} style={{ marginBottom: 10 }}>
                      <div style={{ ...label, marginBottom: 4 }}>{kind} · {rows.length}</div>
                      {rows.slice(0, 5).map(r => (
                        <div key={r.id} style={{ fontSize: 11, color: 'var(--text-2)', padding: '2px 0' }}>
                          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>{r.id}</span>
                          <div style={{ color: 'var(--text)', fontSize: 12 }}>{r.label}</div>
                        </div>
                      ))}
                    </div>
                  )
                ))}
                <button onClick={() => snap.mutate()} style={{ ...primaryBtn, width: '100%', marginTop: 8 }}>
                  Freeze snapshot
                </button>
              </>
            ) : (
              <div style={muted}>Loading evidence…</div>
            )}
          </section>

          <section style={{ ...card, marginTop: 14 }}>
            <h2 style={h2}>Integrity</h2>
            {integrityResult ? (
              integrityResult.checks.map(c => (
                <div key={c.id} style={{ display: 'flex', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                  <span style={{ color: c.passed ? '#10b981' : '#f43f5e', width: 16 }}>{c.passed ? '✓' : '✗'}</span>
                  <div>
                    <div style={{ fontSize: 12 }}>{c.label}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-2)' }}>{c.detail}</div>
                  </div>
                </div>
              ))
            ) : (
              <div style={muted}>Run integrity after drafting sections. Blocks submit on unverified numbers or missing human revision.</div>
            )}
          </section>

          <section style={{ ...card, marginTop: 14 }}>
            <h2 style={h2}>Project source</h2>
            <div style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.5 }}>
              {context?.meta.project_name || 'No project linked'}
              <div style={{ marginTop: 8 }}>
                Metrics in pack: <strong>{context?.summary.metric_count ?? 0}</strong>
              </div>
            </div>
            {pub.project_id && (
              <button onClick={() => navigate(`/projects/${pub.project_id}`)} style={{ ...ghostBtn, width: '100%', marginTop: 10 }}>
                Open project
              </button>
            )}
          </section>
        </aside>
      </div>
    </div>
  )
}

const card: React.CSSProperties = {
  background: 'var(--surface-panel)', border: '1px solid var(--border)',
  borderRadius: 12, padding: 16,
}
const h2: React.CSSProperties = { margin: '0 0 12px', fontSize: 14, color: 'var(--text-heading)' }
const label: React.CSSProperties = {
  fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em',
  color: 'var(--text-dim)', marginBottom: 8, textTransform: 'uppercase',
}
const muted: React.CSSProperties = { fontSize: 12, color: 'var(--text-2)' }
const chip: React.CSSProperties = {
  padding: '4px 9px', borderRadius: 999, fontSize: 11, fontFamily: 'var(--font-mono)',
  border: '1px solid var(--border)', background: 'var(--surface-input)', color: 'var(--text-2)',
}
const input: React.CSSProperties = {
  width: '100%', padding: '8px 10px', fontSize: 13, fontFamily: 'var(--font-mono)',
  background: 'var(--surface-input)', border: '1px solid var(--border)',
  borderRadius: 6, color: 'var(--text)', boxSizing: 'border-box',
}
const primaryBtn: React.CSSProperties = {
  padding: '8px 12px', cursor: 'pointer', fontSize: 12, fontWeight: 700,
  background: '#ff8015', border: 'none', borderRadius: 8, color: '#1a1a1a',
}
const ghostBtn: React.CSSProperties = {
  padding: '7px 12px', cursor: 'pointer', fontSize: 12,
  background: 'transparent', border: '1px solid var(--border)',
  borderRadius: 8, color: 'var(--text-2)',
}
