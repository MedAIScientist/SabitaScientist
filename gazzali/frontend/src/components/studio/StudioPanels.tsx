import { useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { paperApi, type ClaimItem, type IntegrityCheck, type PaperContextSummary } from '../../api'
import { kindLabel } from './studioSteps'

export function Panel({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="card" style={{ padding: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
        <h2 style={{ margin: 0, fontSize: 15 }}>{title}</h2>{action}
      </div>
      {children}
    </section>
  )
}

const muted = { fontSize: 13, color: 'var(--text-3)', margin: 0 } as const

/** What the paper may use, grouped by kind, with what is still missing. */
export function EvidenceView({ context }: { context?: PaperContextSummary }) {
  const [openKind, setOpenKind] = useState<string | null>(null)
  if (!context) return <p style={muted}>Loading your project's results…</p>
  const kinds = Object.entries(context.sources).filter(([, items]) => items.length > 0)
  const gaps = context.summary.warnings
  const last = context.snapshots[0]
  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <p style={{ margin: 0, fontSize: 14 }}>
        {last ? <>✓ Saved on <b>{new Date(last.created_at).toLocaleString()}</b>.</> : 'Not saved yet. Until you save, drafts use whatever is in the project right now.'}
        {' '}{context.summary.metric_count === 0 ? 'No measured numbers yet.' : `${context.summary.metric_count} measured numbers available.`}
      </p>
      <div>
        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 6 }}>What the paper can use</div>
        {kinds.length === 0 ? <p style={muted}>Nothing linked yet. Add experiments or results to the project first.</p> : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {kinds.map(([kind, items]) => (
              <button key={kind} className="chip" style={{ cursor: 'pointer', fontSize: 13, padding: '4px 10px' }} aria-expanded={openKind === kind}
                onClick={() => setOpenKind(openKind === kind ? null : kind)}>
                {items.length} {kindLabel(kind, items.length)} {openKind === kind ? '▴' : '▾'}
              </button>
            ))}
          </div>
        )}
        {openKind && <ul style={{ margin: '8px 0 0', paddingLeft: 18, fontSize: 13 }}>{context.sources[openKind].map(i => <li key={i.id} title={i.id}>{i.label}</li>)}</ul>}
      </div>
      {gaps.length > 0 && (
        <div style={{ borderLeft: '3px solid #f59e0b', paddingLeft: 10 }}>
          <div style={{ fontWeight: 600, fontSize: 14 }}>Worth adding before you write ({gaps.length})</div>
          <p style={{ ...muted, marginBottom: 4 }}>Optional, but each one makes the paper stronger.</p>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>{gaps.map(g => <li key={g}>{g.replace(/^⚠\s*/, '')}</li>)}</ul>
        </div>
      )}
    </div>
  )
}

/** The proposed key points, grouped by section. */
export function KeyPointsView({ claims, onOpenSection }: { claims: ClaimItem[]; onOpenSection: (s: string) => void }) {
  if (claims.length === 0) return <p style={muted}>No key points yet. They appear here a few seconds after you ask for them.</p>
  const bySection = claims.reduce<Record<string, ClaimItem[]>>((acc, c) => ({ ...acc, [c.section]: [...(acc[c.section] ?? []), c] }), {})
  return (
    <div style={{ display: 'grid', gap: 12 }}>
      {Object.entries(bySection).map(([section, items]) => (
        <div key={section}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <b style={{ textTransform: 'capitalize' }}>{section}</b>
            <button className="text-link" style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13 }} onClick={() => onOpenSection(section.toLowerCase())}>Write this section →</button>
          </div>
          <ul style={{ margin: '4px 0 0', paddingLeft: 18, fontSize: 14, lineHeight: 1.5 }}>
            {items.map(c => <li key={c.id}>{c.claim_text} <span style={{ color: c.evidence_ids.length ? 'var(--text-3)' : '#f59e0b', fontSize: 12 }}>
              {c.evidence_ids.length ? `· backed by ${c.evidence_ids.length}` : '· no evidence yet'}</span></li>)}
          </ul>
        </div>
      ))}
    </div>
  )
}

export function FinalCheckView({ checks, passed }: { checks: IntegrityCheck[] | null; passed: boolean | null }) {
  if (!checks) return <p style={muted}>Not run yet. It takes a few seconds and changes nothing in your paper.</p>
  return (
    <div>
      <p style={{ margin: '0 0 8px', fontWeight: 600, color: passed ? '#10b981' : '#f43f5e' }}>{passed ? '✓ Ready to submit' : 'Not ready yet. Fix the items marked ✗ and run it again.'}</p>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 6, fontSize: 14 }}>
        {checks.map(c => (
          <li key={c.id}><span style={{ color: c.passed ? '#10b981' : '#f43f5e' }}>{c.passed ? '✓' : '✗'}</span> {c.label}
            {!c.passed && c.detail && <div style={{ color: 'var(--text-3)', paddingLeft: 18, fontSize: 13 }}>{c.detail}</div>}</li>
        ))}
      </ul>
    </div>
  )
}

/** Reviewer comments as a to-do list: add, mark addressed. */
export function ReviewPointsPanel({ pubId, section }: { pubId: string; section: string }) {
  const qc = useQueryClient()
  const [comment, setComment] = useState('')
  const [action, setAction] = useState('')
  const { data } = useQuery({ queryKey: ['review-points', pubId], queryFn: () => paperApi.reviewPoints(pubId) })
  const refresh = () => qc.invalidateQueries({ queryKey: ['review-points', pubId] })
  const add = useMutation({
    mutationFn: () => paperApi.addReviewPoint(pubId, { comment, action: action || undefined, section }),
    onSuccess: () => { setComment(''); setAction(''); refresh() },
  })
  const toggle = useMutation({
    mutationFn: (p: { id: string; comment: string; action: string | null; section: string | null; status: string }) =>
      paperApi.updateReviewPoint(pubId, p.id, { comment: p.comment, action: p.action ?? undefined, section: p.section ?? undefined,
        status: p.status === 'addressed' ? 'open' : 'addressed' }),
    onSuccess: refresh,
  })
  const points = data?.points ?? []
  const open = points.filter(p => p.status !== 'addressed').length
  return (
    <Panel title="Reviewer comments" action={<span style={{ fontSize: 13, color: 'var(--text-3)' }}>{open} open</span>}>
      <ul style={{ listStyle: 'none', margin: '0 0 8px', padding: 0, display: 'grid', gap: 6, fontSize: 13 }}>
        {points.map(p => (
          <li key={p.id} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
            <input type="checkbox" aria-label={`Addressed: ${p.comment}`} checked={p.status === 'addressed'} onChange={() => toggle.mutate(p)} />
            <span style={{ textDecoration: p.status === 'addressed' ? 'line-through' : 'none', color: p.status === 'addressed' ? 'var(--text-3)' : undefined }}>
              {p.comment}{p.section ? <span style={{ color: 'var(--text-3)' }}> · {p.section}</span> : ''}
              {p.action && <div style={{ color: 'var(--text-3)' }}>→ {p.action}</div>}
            </span>
          </li>
        ))}
        {points.length === 0 && <li style={{ color: 'var(--text-3)' }}>No reviewer comments yet.</li>}
      </ul>
      <textarea className="input" rows={2} placeholder="Paste a reviewer comment" value={comment} onChange={e => setComment(e.target.value)} />
      <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
        <input className="input" placeholder="What you will change (optional)" value={action} onChange={e => setAction(e.target.value)} style={{ flex: 1 }} />
        <button className="btn" disabled={!comment.trim() || add.isPending} onClick={() => add.mutate()}>Add to {section}</button>
      </div>
    </Panel>
  )
}

type Pack = Awaited<ReturnType<typeof paperApi.submitPack>>

export function SubmitPackView({ pack, ready }: { pack: Pack | null; ready: boolean }) {
  if (!pack) return <p style={muted}>{ready ? 'The final check passed. Build the package when you are ready.' : 'You can build it any time; it is complete once the final check passes.'}</p>
  return (
    <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14, lineHeight: 1.6 }}>
      <li>Manuscript: {pack.manuscript.length.toLocaleString()} characters</li>
      <li>{pack.claim_map_size} key points linked to evidence</li>
      <li>Evidence: {pack.evidence_snapshot_id ? 'saved copy included' : 'not saved yet'}</li>
      <li>AI-use statement: {pack.ai_disclosure.ai_versions} AI drafts, {pack.ai_disclosure.human_versions} of your revisions</li>
      <li style={{ color: pack.integrity_passed ? '#10b981' : '#f43f5e' }}>Final check {pack.integrity_passed ? 'passed' : 'not passed yet'}</li>
      <li>{pack.open_review_points} reviewer comments still open</li>
    </ul>
  )
}
