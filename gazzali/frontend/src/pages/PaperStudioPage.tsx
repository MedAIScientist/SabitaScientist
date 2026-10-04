import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, paperApi, type IntegrityCheck } from '../api'
import { SectionEditor } from '../components/studio/SectionEditor'
import { EvidencePanel, IntegrityPanel, ReviewPointsPanel, SubmitPackPanel } from '../components/studio/StudioPanels'
import { STEPS, nextStep, progress } from '../components/studio/studioSteps'

const SECTIONS = ['abstract', 'introduction', 'related work', 'methods', 'results', 'discussion', 'conclusion']

/**
 * Paper Studio: write a paper step by step from frozen evidence. One "next step"
 * at a time; every claim is tied to evidence; your own revision is required.
 */
export function PaperStudioPage() {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [section, setSection] = useState('introduction')
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)
  const [integrity, setIntegrity] = useState<{ passed: boolean; checks: IntegrityCheck[] } | null>(null)
  const [pack, setPack] = useState<Awaited<ReturnType<typeof paperApi.submitPack>> | null>(null)

  const { data: pub, isLoading } = useQuery({ queryKey: ['publication', id], queryFn: () => api.getPublication(id), enabled: !!id })
  const { data: stages } = useQuery({ queryKey: ['paper-stages', id], queryFn: () => paperApi.stages(id), enabled: !!id })
  const { data: context } = useQuery({ queryKey: ['paper-context', id], queryFn: () => paperApi.context(id), enabled: !!id })
  const { data: outline } = useQuery({ queryKey: ['paper-outline', id], queryFn: () => paperApi.outline(id), enabled: !!id })
  const { data: versions = [] } = useQuery({ queryKey: ['pub-versions', id], queryFn: () => api.listVersions(id), enabled: !!id })

  const refresh = (...keys: string[]) => { for (const k of [...keys, 'paper-stages']) qc.invalidateQueries({ queryKey: [k, id] }) }
  const fail = (e: Error) => setNotice({ text: e.message, error: true })
  const snap = useMutation({ mutationFn: () => paperApi.snapshot(id, 'Evidence pack'), onError: fail,
    onSuccess: () => { setNotice({ text: 'Evidence frozen. Drafts now cite this snapshot.' }); refresh('paper-context') } })
  const genOutline = useMutation({ mutationFn: () => paperApi.generateOutline(id), onError: fail,
    onSuccess: r => { setNotice({ text: `Outline ready: ${r.claims.length} claims tied to evidence.` }); refresh('paper-outline') } })
  const draft = useMutation({ mutationFn: () => paperApi.draftSection(id, section, 'academic'), onError: fail,
    onSuccess: r => { setNotice({ text: `Drafting ${section} from ${r.claim_count} claims. It appears here when done.` }); refresh('pub-versions') } })
  const coherence = useMutation({ mutationFn: () => paperApi.coherence(id), onError: fail,
    onSuccess: () => { setNotice({ text: 'Coherence pass started.' }); refresh('pub-versions') } })
  const runIntegrity = useMutation({ mutationFn: () => paperApi.integrity(id), onError: fail,
    onSuccess: r => { setIntegrity(r); setNotice({ text: r.passed ? 'Integrity passed.' : `Not ready: ${r.blocking.join(', ')}`, error: !r.passed }); refresh() } })
  const buildPack = useMutation({ mutationFn: () => paperApi.submitPack(id), onError: fail, onSuccess: setPack })

  if (isLoading) return <div style={{ padding: 32, color: 'var(--text-2)' }}>Loading Paper Studio…</div>
  if (!pub) return <div style={{ padding: 32 }}>Publication not found.</div>

  const flags = stages?.stages ?? {}
  const next = nextStep(flags)
  const { done, total } = progress(flags)
  const claims = outline?.claims ?? []
  const sectionsDone = new Set((stages?.sections_done ?? []).map(s => s.toLowerCase()))
  const checks = integrity?.checks ?? stages?.integrity?.checks ?? null
  const passed = integrity?.passed ?? stages?.integrity?.passed ?? null
  const busy = snap.isPending || genOutline.isPending || draft.isPending || coherence.isPending || runIntegrity.isPending || buildPack.isPending

  const runStep = (key: string) => ({
    setup: () => navigate(`/publications/${id}`), evidence: () => snap.mutate(), outline: () => genOutline.mutate(),
    sections: () => draft.mutate(), coherence: () => coherence.mutate(), integrity: () => runIntegrity.mutate(), submit: () => buildPack.mutate(),
  } as Record<string, () => void>)[key]?.()

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <header style={{ position: 'sticky', top: 0, zIndex: 10, background: 'var(--surface-header)', borderBottom: '1px solid var(--border)', padding: '10px 24px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <button className="btn" onClick={() => navigate(`/publications/${id}`)}>← Paper</button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 style={{ margin: 0, fontSize: 17, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{pub.title}</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-3)' }}>
            <span>Paper Studio · {done}/{total} steps</span>
            <span style={{ width: 120, height: 5, background: 'var(--border)', borderRadius: 3 }} aria-hidden>
              <span style={{ display: 'block', width: `${(done / total) * 100}%`, height: 5, background: 'var(--accent)', borderRadius: 3 }} />
            </span>
          </div>
        </div>
      </header>

      <div style={{ padding: '16px 24px', display: 'grid', gap: 14 }}>
        {next && (
          <section className="card" role="status" style={{ padding: '12px 16px', display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap', borderLeft: '4px solid var(--accent)' }}>
            <div style={{ flex: 1, minWidth: 260 }}>
              <div style={{ fontSize: 12, color: 'var(--text-3)' }}>Next step · {STEPS.indexOf(next) + 1} of {total}</div>
              <div style={{ fontWeight: 700 }}>{next.title}</div>
              <div style={{ fontSize: 13, color: 'var(--text-2)' }}>{next.explain}</div>
            </div>
            <button className="btn btn-primary" disabled={busy} onClick={() => runStep(next.key)}>
              {next.key === 'sections' ? `Draft ${section}` : next.action}
            </button>
          </section>
        )}
        {notice && (
          <div className={notice.error ? 'msg msg-error' : 'msg'} role={notice.error ? 'alert' : 'status'} style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>{notice.text}</span><button className="btn" onClick={() => setNotice(null)} aria-label="Dismiss">×</button>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '200px minmax(0, 1fr) 340px', gap: 14, alignItems: 'start' }}>
          <nav aria-label="Pipeline" className="card" style={{ padding: 10 }}>
            {STEPS.map((s, i) => {
              const isDone = !!flags[s.key]
              const isNext = next?.key === s.key
              return (
                <button key={s.key} onClick={() => runStep(s.key)} disabled={busy} title={s.explain}
                  style={{ display: 'flex', gap: 8, width: '100%', textAlign: 'left', padding: '7px 6px', border: 'none', borderRadius: 6, cursor: 'pointer',
                    background: isNext ? 'rgba(var(--accent-rgb, 99,102,241),0.12)' : 'transparent', color: 'var(--text)', fontWeight: isNext ? 700 : 400 }}>
                  <span style={{ color: isDone ? '#10b981' : 'var(--text-3)' }}>{isDone ? '✓' : i + 1}</span>{s.title}
                </button>
              )
            })}
          </nav>

          <main style={{ display: 'grid', gap: 10, minWidth: 0 }}>
            <div role="tablist" aria-label="Sections" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {SECTIONS.map(s => (
                <button key={s} role="tab" aria-selected={section === s} className="chip" onClick={() => setSection(s)}
                  style={{ cursor: 'pointer', fontWeight: section === s ? 700 : 400, outline: section === s ? '2px solid var(--accent)' : 'none' }}>
                  {sectionsDone.has(s) ? '● ' : '○ '}{s}
                </button>
              ))}
            </div>
            <SectionEditor pubId={id} section={section}
              claims={claims.filter(c => c.section.toLowerCase() === section)}
              versions={versions.filter(v => (v.section ?? '').toLowerCase() === section || v.section === 'full-draft')}
              onDraft={() => draft.mutate()} drafting={draft.isPending} canDraft={claims.length > 0} />
          </main>

          <aside style={{ display: 'grid', gap: 10 }}>
            <EvidencePanel context={context} onFreeze={() => snap.mutate()} freezing={snap.isPending} />
            <IntegrityPanel checks={checks} passed={passed} onRun={() => runIntegrity.mutate()} running={runIntegrity.isPending} />
            <SubmitPackPanel pack={pack} onBuild={() => buildPack.mutate()} building={buildPack.isPending} ready={!!passed} />
            <ReviewPointsPanel pubId={id} section={section} />
          </aside>
        </div>
      </div>
    </div>
  )
}
