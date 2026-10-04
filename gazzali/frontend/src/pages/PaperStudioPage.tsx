import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, paperApi, type IntegrityCheck, type Version } from '../api'
import { SectionEditor } from '../components/studio/SectionEditor'
import { EvidenceView, FinalCheckView, KeyPointsView, ReviewPointsPanel, SubmitPackView } from '../components/studio/StudioPanels'
import { STEPS, nextStep, progress, type Step } from '../components/studio/studioSteps'

const SECTIONS = ['abstract', 'introduction', 'related work', 'methods', 'results', 'discussion', 'conclusion']
const WAIT_MS = 4 * 60_000

/** AI notes from the "read it as a whole" pass (saved as a version with section "coherence"). */
function FlowNotes({ pubId, versions }: { pubId: string; versions: Version[] }) {
  const latest = versions.find(v => v.section === 'coherence' && (v.content_length || 0) > 0)
  const { data } = useQuery({ queryKey: ['version-content', pubId, latest?.id], queryFn: () => api.getVersion(pubId, latest!.id), enabled: !!latest })
  if (!latest) return <p style={{ fontSize: 13, color: 'var(--text-3)', margin: 0 }}>No feedback yet. Write at least the main sections first, then ask for it.</p>
  return (
    <div>
      <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 6 }}>Feedback from {new Date(latest.created_at).toLocaleString()}</div>
      <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6, fontSize: 14, maxHeight: 520, overflow: 'auto' }}>{data?.content ?? 'Loading…'}</div>
    </div>
  )
}

/**
 * Paper Studio: write a paper one step at a time from saved evidence.
 * Left: the steps. Right: the selected step — what it does, its one action, its result.
 */
export function PaperStudioPage() {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [viewKey, setViewKey] = useState<string | null>(null)
  const [section, setSection] = useState('introduction')
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)
  const [integrity, setIntegrity] = useState<{ passed: boolean; checks: IntegrityCheck[] } | null>(null)
  const [pack, setPack] = useState<Awaited<ReturnType<typeof paperApi.submitPack>> | null>(null)
  // AI jobs run in the background; poll until a new version shows up.
  const [waiting, setWaiting] = useState<{ label: string; baseline: number; until: number } | null>(null)

  const { data: pub, isLoading } = useQuery({ queryKey: ['publication', id], queryFn: () => api.getPublication(id), enabled: !!id })
  const { data: stages } = useQuery({ queryKey: ['paper-stages', id], queryFn: () => paperApi.stages(id), enabled: !!id, refetchInterval: waiting ? 5000 : false })
  const { data: context } = useQuery({ queryKey: ['paper-context', id], queryFn: () => paperApi.context(id), enabled: !!id })
  const { data: outline } = useQuery({ queryKey: ['paper-outline', id], queryFn: () => paperApi.outline(id), enabled: !!id })
  const { data: versions = [] } = useQuery({ queryKey: ['pub-versions', id], queryFn: () => api.listVersions(id), enabled: !!id, refetchInterval: waiting ? 5000 : false })

  useEffect(() => {
    if (!waiting) return
    if (versions.length > waiting.baseline) { setNotice({ text: `${waiting.label} is ready.` }); setWaiting(null) }
    else if (Date.now() > waiting.until) { setNotice({ text: `${waiting.label} is taking longer than usual. It will appear when you come back.` }); setWaiting(null) }
  }, [versions.length, waiting])

  const refresh = (...keys: string[]) => { for (const k of [...keys, 'paper-stages']) qc.invalidateQueries({ queryKey: [k, id] }) }
  const fail = (e: Error) => setNotice({ text: e.message, error: true })
  const wait = (label: string) => setWaiting({ label, baseline: versions.length, until: Date.now() + WAIT_MS })
  const snap = useMutation({ mutationFn: () => paperApi.snapshot(id, 'Evidence pack'), onError: fail,
    onSuccess: () => { setNotice({ text: 'Evidence saved. Next, plan the key points.' }); refresh('paper-context') } })
  const genOutline = useMutation({ mutationFn: () => paperApi.generateOutline(id), onError: fail,
    onSuccess: r => { setNotice({ text: `${r.claims.length} key points suggested. Read them, then start writing.` }); refresh('paper-outline') } })
  const draft = useMutation({ mutationFn: () => paperApi.draftSection(id, section, 'academic'), onError: fail,
    onSuccess: () => { wait(`The ${section} draft`); refresh('pub-versions') } })
  const coherence = useMutation({ mutationFn: () => paperApi.coherence(id), onError: fail,
    onSuccess: () => { wait('Feedback on the flow'); refresh('pub-versions') } })
  const runIntegrity = useMutation({ mutationFn: () => paperApi.integrity(id), onError: fail,
    onSuccess: r => { setIntegrity(r); setNotice(r.passed ? { text: 'All checks passed. You can build the package.' } : { text: 'Some checks did not pass. See the list below.', error: true }); refresh() } })
  const buildPack = useMutation({ mutationFn: () => paperApi.submitPack(id), onError: fail, onSuccess: setPack })

  if (isLoading) return <div style={{ padding: 32, color: 'var(--text-2)' }}>Loading Paper Studio…</div>
  if (!pub) return <div style={{ padding: 32 }}>Paper not found.</div>

  const flags = stages?.stages ?? {}
  const next = nextStep(flags)
  const { done, total } = progress(flags)
  const view: Step = STEPS.find(s => s.key === viewKey) ?? next ?? STEPS[STEPS.length - 1]
  const viewIndex = STEPS.indexOf(view)
  const claims = outline?.claims ?? []
  const sectionsDone = new Set((stages?.sections_done ?? []).map(s => s.toLowerCase()))
  const checks = integrity?.checks ?? stages?.integrity?.checks ?? null
  const passed = integrity?.passed ?? stages?.integrity?.passed ?? null
  const busy = snap.isPending || genOutline.isPending || draft.isPending || coherence.isPending || runIntegrity.isPending || buildPack.isPending
  const go = (key: string) => { setViewKey(key); setNotice(null) }
  const openSection = (s: string) => { setSection(SECTIONS.includes(s) ? s : 'introduction'); go('sections') }

  const actions: Record<string, { run: () => void; pending: boolean; blocked?: string }> = {
    setup: { run: () => navigate(`/publications/${id}`), pending: false },
    evidence: { run: () => snap.mutate(), pending: snap.isPending },
    outline: { run: () => genOutline.mutate(), pending: genOutline.isPending, blocked: flags.evidence ? undefined : 'Save your evidence first.' },
    coherence: { run: () => coherence.mutate(), pending: coherence.isPending, blocked: flags.sections ? undefined : 'Write the main sections first.' },
    integrity: { run: () => runIntegrity.mutate(), pending: runIntegrity.isPending },
    submit: { run: () => buildPack.mutate(), pending: buildPack.isPending },
  }
  const action = actions[view.key] // the sections step acts from inside the editor
  const isDone = !!flags[view.key]

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <header style={{ position: 'sticky', top: 0, zIndex: 10, background: 'var(--surface-header)', borderBottom: '1px solid var(--border)', padding: '10px 24px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <button className="btn" onClick={() => navigate(`/publications/${id}`)}>← Back to paper</button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 style={{ margin: 0, fontSize: 17, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{pub.title}</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-3)' }}>
            <span>{next ? `${done} of ${total} steps done` : 'All steps done'}</span>
            <span style={{ width: 140, height: 6, background: 'var(--border)', borderRadius: 3 }} aria-hidden>
              <span style={{ display: 'block', width: `${(done / total) * 100}%`, height: 6, background: 'var(--accent)', borderRadius: 3 }} />
            </span>
          </div>
        </div>
      </header>

      <div style={{ padding: '16px 24px', display: 'grid', gridTemplateColumns: 'minmax(200px, 240px) minmax(0, 1fr)', gap: 16, alignItems: 'start', maxWidth: 1280 }}>
        <nav aria-label="Steps" className="card" style={{ padding: 8, position: 'sticky', top: 76 }}>
          <ol style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            {STEPS.map((s, i) => {
              const sDone = !!flags[s.key]
              const current = view.key === s.key
              return (
                <li key={s.key}>
                  <button onClick={() => go(s.key)} aria-current={current ? 'step' : undefined}
                    style={{ display: 'flex', gap: 10, alignItems: 'center', width: '100%', textAlign: 'left', padding: '9px 8px', border: 'none', borderRadius: 8, cursor: 'pointer',
                      background: current ? 'var(--surface-2, rgba(127,127,127,0.12))' : 'transparent', color: 'var(--text)' }}>
                    <span aria-hidden style={{ width: 22, height: 22, flex: 'none', borderRadius: '50%', display: 'grid', placeItems: 'center', fontSize: 12, fontWeight: 700,
                      background: sDone ? '#10b981' : next?.key === s.key ? 'var(--accent)' : 'transparent', color: sDone || next?.key === s.key ? '#fff' : 'var(--text-3)',
                      border: sDone || next?.key === s.key ? 'none' : '1px solid var(--border)' }}>{sDone ? '✓' : i + 1}</span>
                    <span style={{ flex: 1 }}>
                      <span style={{ display: 'block', fontWeight: current ? 700 : 500, fontSize: 14 }}>{s.title}</span>
                      <span style={{ fontSize: 11, color: sDone ? '#10b981' : next?.key === s.key ? 'var(--accent)' : 'var(--text-3)' }}>
                        {sDone ? 'Done' : next?.key === s.key ? 'Do this next' : 'Not started'}
                      </span>
                    </span>
                  </button>
                </li>
              )
            })}
          </ol>
        </nav>

        <main style={{ display: 'grid', gap: 12, minWidth: 0 }}>
          {next && next.key !== view.key && (
            <div className="msg" role="status" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
              <span>Your next step is <b>{next.title}</b>.</span>
              <button className="btn" onClick={() => go(next.key)}>Go there →</button>
            </div>
          )}
          {waiting && <div className="msg" role="status">⏳ {waiting.label} is being written by AI. This usually takes a minute; it appears here by itself.</div>}
          {notice && (
            <div className={notice.error ? 'msg msg-error' : 'msg'} role={notice.error ? 'alert' : 'status'} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>{notice.text}</span><button className="btn" onClick={() => setNotice(null)} aria-label="Dismiss">×</button>
            </div>
          )}

          <section className="card" style={{ padding: '16px 18px' }}>
            <div style={{ fontSize: 12, color: 'var(--text-3)' }}>Step {viewIndex + 1} of {total}{view.ai ? ' · uses AI' : ''}</div>
            <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap', justifyContent: 'space-between' }}>
              <div style={{ flex: 1, minWidth: 280 }}>
                <h2 style={{ margin: '2px 0 6px', fontSize: 20 }}>{view.title}</h2>
                <p style={{ margin: 0, color: 'var(--text-2)', fontSize: 14, lineHeight: 1.5 }}>{view.explain}</p>
                {isDone && <p style={{ margin: '8px 0 0', color: '#10b981', fontSize: 14 }}>✓ {view.done}</p>}
              </div>
              {action && (
                <div style={{ display: 'grid', justifyItems: 'end', gap: 4 }}>
                  <button className={isDone ? 'btn' : 'btn btn-primary'} disabled={busy || !!action.blocked} onClick={action.run}>
                    {action.pending ? 'Working…' : isDone && view.key !== 'setup' ? `${view.action} again` : view.action}
                  </button>
                  {action.blocked && <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{action.blocked}</span>}
                </div>
              )}
            </div>
          </section>

          {view.key === 'setup' && (
            <section className="card" style={{ padding: 16, fontSize: 14 }}>
              <b>Title:</b> {pub.title || '—'}
            </section>
          )}
          {view.key === 'evidence' && <section className="card" style={{ padding: 16 }}><EvidenceView context={context} /></section>}
          {view.key === 'outline' && <section className="card" style={{ padding: 16 }}><KeyPointsView claims={claims} onOpenSection={openSection} /></section>}
          {view.key === 'sections' && (
            <>
              <div role="tablist" aria-label="Sections" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {SECTIONS.map(s => {
                  const n = claims.filter(c => c.section.toLowerCase() === s).length
                  const has = sectionsDone.has(s)
                  return (
                    <button key={s} role="tab" aria-selected={section === s} onClick={() => setSection(s)} className="btn"
                      style={{ textTransform: 'capitalize', fontWeight: section === s ? 700 : 400, borderColor: section === s ? 'var(--accent)' : undefined,
                        boxShadow: section === s ? '0 0 0 1px var(--accent)' : 'none' }}>
                      <span style={{ color: has ? '#10b981' : 'var(--text-3)', marginRight: 6 }} aria-label={has ? 'has text' : 'empty'}>{has ? '✓' : '○'}</span>
                      {s}{n > 0 && <span style={{ color: 'var(--text-3)', fontSize: 12, marginLeft: 4 }}>({n})</span>}
                    </button>
                  )
                })}
              </div>
              <SectionEditor pubId={id} section={section}
                claims={claims.filter(c => c.section.toLowerCase() === section)}
                versions={versions.filter(v => (v.section ?? '').toLowerCase() === section || v.section === 'full-draft')}
                onDraft={() => draft.mutate()} drafting={draft.isPending || !!waiting} canDraft={claims.length > 0} />
              <details className="card" style={{ padding: '10px 14px' }}>
                <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Reviewer comments for this paper</summary>
                <div style={{ marginTop: 8 }}><ReviewPointsPanel pubId={id} section={section} /></div>
              </details>
            </>
          )}
          {view.key === 'coherence' && <section className="card" style={{ padding: 16 }}><FlowNotes pubId={id} versions={versions} /></section>}
          {view.key === 'integrity' && <section className="card" style={{ padding: 16 }}><FinalCheckView checks={checks} passed={passed} /></section>}
          {view.key === 'submit' && (
            <>
              <section className="card" style={{ padding: 16 }}><SubmitPackView pack={pack} ready={!!passed} /></section>
              <ReviewPointsPanel pubId={id} section={section} />
            </>
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            {viewIndex > 0 ? <button className="btn" onClick={() => go(STEPS[viewIndex - 1].key)}>← {STEPS[viewIndex - 1].title}</button> : <span />}
            {viewIndex < total - 1 && <button className="btn" onClick={() => go(STEPS[viewIndex + 1].key)}>{STEPS[viewIndex + 1].title} →</button>}
          </div>
        </main>
      </div>
    </div>
  )
}
