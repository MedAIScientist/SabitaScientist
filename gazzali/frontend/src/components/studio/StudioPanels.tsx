import { useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { paperApi, type IntegrityCheck, type PaperContextSummary } from '../../api'
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

/** What the paper may cite, grouped by kind; gaps folded into one summary. */
export function EvidencePanel({ context, onFreeze, freezing }: { context?: PaperContextSummary; onFreeze: () => void; freezing: boolean }) {
  const [openKind, setOpenKind] = useState<string | null>(null)
  const [showGaps, setShowGaps] = useState(false)
  if (!context) return <Panel title="Evidence">Loading…</Panel>
  const kinds = Object.entries(context.sources).filter(([, items]) => items.length > 0)
  const gaps = context.summary.warnings
  const last = context.snapshots[0]
  return (
    <Panel title="Evidence" action={<button className="btn" disabled={freezing} onClick={onFreeze}>{freezing ? 'Freezing…' : last ? 'Refreeze' : 'Freeze'}</button>}>
      <p style={{ fontSize: 13, color: 'var(--text-3)', margin: '0 0 8px' }}>
        {last ? `Frozen ${new Date(last.created_at).toLocaleString()}` : 'Not frozen yet: drafts cite the live project.'} · {context.summary.metric_count} measured results
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {kinds.map(([kind, items]) => (
          <button key={kind} className="chip" style={{ cursor: 'pointer' }} aria-expanded={openKind === kind} onClick={() => setOpenKind(openKind === kind ? null : kind)}>
            {items.length} {kindLabel(kind, items.length)}
          </button>
        ))}
        {kinds.length === 0 && <span style={{ fontSize: 13, color: 'var(--text-3)' }}>No evidence linked yet.</span>}
      </div>
      {openKind && (
        <ul style={{ margin: '8px 0 0', paddingLeft: 18, fontSize: 13 }}>
          {context.sources[openKind].map(i => <li key={i.id} title={i.id}>{i.label}</li>)}
        </ul>
      )}
      {gaps.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <button className="text-link" style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: '#f59e0b' }}
            aria-expanded={showGaps} onClick={() => setShowGaps(v => !v)}>
            {gaps.length} gap{gaps.length > 1 ? 's' : ''} to fill {showGaps ? '▴' : '▾'}
          </button>
          {showGaps && <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 13 }}>{gaps.map(g => <li key={g}>{g.replace(/^⚠\s*/, '')}</li>)}</ul>}
        </div>
      )}
    </Panel>
  )
}

export function IntegrityPanel({ checks, passed, onRun, running }: { checks: IntegrityCheck[] | null; passed: boolean | null; onRun: () => void; running: boolean }) {
  return (
    <Panel title="Integrity" action={<button className="btn" disabled={running} onClick={onRun}>{running ? 'Checking…' : checks ? 'Run again' : 'Run'}</button>}>
      {!checks ? <p style={{ fontSize: 13, color: 'var(--text-3)', margin: 0 }}>Checks unverified numbers, citations and human revision before submission.</p> : (
        <>
          <p style={{ margin: '0 0 6px', fontWeight: 600, color: passed ? '#10b981' : '#f43f5e' }}>{passed ? 'Ready to submit' : 'Not ready yet'}</p>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 4, fontSize: 13 }}>
            {checks.map(c => (
              <li key={c.id}><span style={{ color: c.passed ? '#10b981' : '#f43f5e' }}>{c.passed ? '✓' : '✗'}</span> {c.label}
                {!c.passed && c.detail && <div style={{ color: 'var(--text-3)', paddingLeft: 16 }}>{c.detail}</div>}</li>
            ))}
          </ul>
        </>
      )}
    </Panel>
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

export function SubmitPackPanel({ pack, onBuild, building, ready }: { pack: Pack | null; onBuild: () => void; building: boolean; ready: boolean }) {
  return (
    <Panel title="Submission pack" action={<button className={ready ? 'btn btn-primary' : 'btn'} disabled={building} onClick={onBuild}>{building ? 'Building…' : 'Build'}</button>}>
      {!pack ? <p style={{ fontSize: 13, color: 'var(--text-3)', margin: 0 }}>{ready ? 'Integrity passed: build the pack.' : 'Available after the integrity check passes.'}</p> : (
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
          <li>Manuscript: {pack.manuscript.length.toLocaleString()} characters</li>
          <li>{pack.claim_map_size} claims mapped to evidence</li>
          <li>Evidence snapshot: {pack.evidence_snapshot_id ? 'frozen' : 'not frozen'}</li>
          <li>AI disclosure: {pack.ai_disclosure.ai_versions} AI / {pack.ai_disclosure.human_versions} human versions</li>
          <li style={{ color: pack.integrity_passed ? '#10b981' : '#f43f5e' }}>Integrity {pack.integrity_passed ? 'passed' : 'not passed'}</li>
          <li>{pack.open_review_points} open reviewer comments</li>
        </ul>
      )}
    </Panel>
  )
}
