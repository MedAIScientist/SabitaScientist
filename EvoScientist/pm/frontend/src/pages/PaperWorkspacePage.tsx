import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AiUsagePanel } from '../components/AiUsagePanel'
import { api, supervisionApi } from '../api'

const STAGES: Record<string, { label: string; color: string; tools: string[] }> = {
  draft: { label: 'Writing', color: '#8b5cf6', tools: ['section', 'experiment', 'revise', 'hypothesis'] },
  submitted: { label: 'Submitted', color: '#6366f1', tools: ['rebuttal', 'revise'] },
  reviewing: { label: 'Under review', color: '#f59e0b', tools: ['rebuttal', 'revise'] },
  accepted: { label: 'Accepted', color: '#10b981', tools: ['figures'] },
  published: { label: 'Published', color: '#10b981', tools: ['figures'] },
  rejected: { label: 'Rejected', color: '#f43f5e', tools: ['revise', 'section'] },
}

const SECTIONS = ['abstract', 'introduction', 'methods', 'results', 'discussion', 'conclusion']

/**
 * Paper workspace — stage-aware drafting, readiness gate, and weekly evidence.
 * Layout: editor spine on the left, decision rail on the right.
 */
export function PaperWorkspacePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [section, setSection] = useState('introduction')
  const [style, setStyle] = useState('academic')
  const [notice, setNotice] = useState<string | null>(null)
  // Submission compliance statements. Seeded from the publication once it loads,
  // then owned by the form so typing does not fight the refetch.
  const [compliance, setCompliance] = useState<Record<string, string> | null>(null)

  const { data: pub, isLoading } = useQuery({
    queryKey: ['publication', id],
    queryFn: () => api.getPublication(id!),
    enabled: !!id,
  })
  const { data: readiness } = useQuery({
    queryKey: ['paper-readiness', id],
    queryFn: () => supervisionApi.paperReadiness(id!),
    enabled: !!id,
  })
  const { data: evidence } = useQuery({
    queryKey: ['paper-evidence', id],
    queryFn: () => supervisionApi.paperEvidence(id!),
    enabled: !!id,
  })
  const { data: versions } = useQuery({
    queryKey: ['pub-versions', id],
    queryFn: () => api.listVersions(id!),
    enabled: !!id,
  })

  const draftSection = useMutation({
    mutationFn: () => api.draftSection(id!, section, style),
    onSuccess: () => {
      setNotice(`Section draft started: ${section}`)
      qc.invalidateQueries({ queryKey: ['pub-versions', id] })
    },
    onError: (e: Error) => setNotice(e.message),
  })

  const stage = STAGES[(pub?.status || 'draft') as keyof typeof STAGES] || STAGES.draft
  useEffect(() => {
    if (!pub || compliance) return
    setCompliance({
      reporting_guideline: pub.reporting_guideline ?? '',
      data_availability: pub.data_availability ?? '',
      code_availability: pub.code_availability ?? '',
      conflict_of_interest: pub.conflict_of_interest ?? '',
      funding_statement: pub.funding_statement ?? '',
    })
  }, [pub, compliance])

  const suggested = readiness?.suggested_tools || stage.tools
  const pct = readiness?.readiness_pct ?? 0

  const openQuestions = useMemo(() => evidence?.open_questions || [], [evidence])

  if (isLoading) return <div style={{ padding: 32, color: 'var(--text-2)' }}>Loading paper workspace…</div>
  if (!pub) return <div style={{ padding: 32 }}>Publication not found.</div>

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      {/* Top bar */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 10,
        background: 'var(--surface-header)', borderBottom: '1px solid var(--border)',
        padding: '12px 28px', display: 'flex', alignItems: 'center', gap: 14,
      }}>
        <button onClick={() => navigate(`/publications/${id}`)} style={ghostBtn}>← Back</button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h1 style={{
              margin: 0, fontSize: 15, color: 'var(--text-heading)',
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            }}>{pub.title}</h1>
            <span style={{
              fontSize: 11, fontFamily: 'var(--font-mono)', padding: '3px 10px',
              borderRadius: 999, color: stage.color, background: `${stage.color}18`,
              border: `1px solid ${stage.color}44`, letterSpacing: '0.04em',
            }}>{stage.label.toUpperCase()}</span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 2 }}>
            {pub.venue || 'No venue'} · {readiness?.ai_versions ?? 0} AI / {readiness?.human_versions ?? 0} human versions
          </div>
        </div>
        <ReadinessRing pct={pct} />
      </div>

      {notice && (
        <div style={{
          margin: '14px 28px 0', padding: '10px 14px', borderRadius: 8,
          background: 'rgba(var(--accent-rgb),0.1)', border: '1px solid rgba(var(--accent-rgb),0.28)',
          color: 'var(--text)', fontSize: 13,
        }}>{notice}</div>
      )}

      <div style={{
        display: 'grid', gridTemplateColumns: '1.45fr 360px', gap: 20,
        padding: '20px 28px 40px', maxWidth: 1280, margin: '0 auto',
      }}>
        {/* Editor spine */}
        <div>
          {/* Stage-aware tools */}
          <section style={card}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h2 style={h2}>Draft tools</h2>
              <span style={muted}>Suggestions match stage</span>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {suggested.includes('section') && (
                <button onClick={() => draftSection.mutate()} disabled={draftSection.isPending} style={primaryBtn}>
                  {draftSection.isPending ? 'Drafting…' : `Draft ${section}`}
                </button>
              )}
              {suggested.includes('experiment') && (
                <button
                  onClick={() => {
                    const expId = evidence?.linked_experiments?.[0]?.experiment_id
                    if (!expId || !pub.project_id) return setNotice('Link an experiment first')
                    api.draftFromExperiment(pub.project_id, expId, section, style)
                      .then(() => setNotice(`Experiment→${section} draft started`))
                      .catch((e: Error) => setNotice(e.message))
                  }}
                  style={ghostBtn}
                >From experiment →</button>
              )}
              {suggested.includes('rebuttal') && (
                <button
                  onClick={() => navigate(`/publications/${id}`)}
                  style={ghostBtn}
                >Reviewer response</button>
              )}
              {suggested.includes('revise') && (
                <button onClick={() => navigate(`/publications/${id}`)} style={ghostBtn}>Revise text</button>
              )}
              {suggested.includes('hypothesis') && (
                <button onClick={() => navigate(`/publications/${id}`)} style={ghostBtn}>Hypotheses</button>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 160px', gap: 10, marginTop: 14 }}>
              <div>
                <div style={label}>Target section</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {SECTIONS.map(s => (
                    <button
                      key={s}
                      onClick={() => setSection(s)}
                      style={{
                        ...chip,
                        background: section === s ? 'rgba(var(--accent-rgb),0.15)' : 'var(--surface-input)',
                        borderColor: section === s ? 'rgba(var(--accent-rgb),0.45)' : 'var(--border)',
                        color: section === s ? 'var(--accent)' : 'var(--text-2)',
                      }}
                    >{s}</button>
                  ))}
                </div>
                <div style={{ ...muted, marginTop: 8 }}>
                  Evidence is scoped to experiments linked to this section when links exist.
                </div>
              </div>
              <div>
                <div style={label}>Style</div>
                <select value={style} onChange={e => setStyle(e.target.value)} style={select}>
                  <option value="academic">academic</option>
                  <option value="concise">concise</option>
                  <option value="technical">technical</option>
                </select>
              </div>
            </div>
          </section>

          {/* Evidence (compact) */}
          <section style={{ ...card, marginTop: 16 }}>
            <h2 style={h2}>Evidence for this paper</h2>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '10px 0 14px' }}>
              {(evidence?.linked_experiments || []).map(ex => (
                <span key={ex.experiment_id} style={{
                  ...chip, background: 'rgba(139,92,246,0.12)', borderColor: 'rgba(139,92,246,0.35)', color: '#c4b5fd',
                }}>
                  {ex.experiment_name}{ex.section ? ` → ${ex.section}` : ''}
                </span>
              ))}
              {!evidence?.linked_experiments?.length && (
                <span style={muted}>No experiments linked yet — use Research items to attach evidence.</span>
              )}
            </div>
            {(evidence?.weekly_updates || []).slice(0, 6).map(w => (
              <div key={w.id} style={{
                padding: '10px 12px', borderRadius: 8, marginBottom: 8,
                background: 'var(--surface-input)', border: '1px solid var(--border)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <strong style={{ fontSize: 13 }}>{w.item_title}</strong>
                  <span style={{ ...muted, fontFamily: 'var(--font-mono)' }}>{w.week_start}</span>
                </div>
                {w.what_changed && <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 4 }}>{w.what_changed}</div>}
                <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 4 }}>
                  {w.progress_pct}% · {w.status || 'update'}{w.needs_help ? ' · needs help' : ''}
                </div>
              </div>
            ))}
            {!evidence?.weekly_updates?.length && (
              <div style={muted}>No weekly updates linked to this paper yet.</div>
            )}
          </section>

          {/* Versions */}
          <section style={{ ...card, marginTop: 16 }}>
            <h2 style={h2}>Draft history</h2>
            {(versions || []).slice(0, 8).map(v => (
              <div key={v.id} style={{
                display: 'flex', gap: 12, alignItems: 'center', padding: '10px 0',
                borderBottom: '1px solid var(--border)', fontSize: 13,
              }}>
                <span style={{
                  fontSize: 10, fontFamily: 'var(--font-mono)', padding: '2px 8px', borderRadius: 999,
                  background: (v.generated_by || '').startsWith('ai') ? 'rgba(var(--accent-rgb),0.12)' : 'var(--surface-input)',
                  color: (v.generated_by || '').startsWith('ai') ? 'var(--accent)' : 'var(--text-2)',
                  border: '1px solid var(--border)',
                }}>{v.generated_by || 'human'}</span>
                <span style={{ flex: 1, color: 'var(--text)' }}>{v.notes || v.section || 'version'}</span>
                <span style={muted}>{(v.created_at || '').slice(0, 16).replace('T', ' ')}</span>
              </div>
            ))}
            {!versions?.length && <div style={muted}>No versions yet.</div>}
          </section>
        </div>

        {/* Decision rail */}
        <aside>
          <section style={card}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ ...h2, marginBottom: 0 }}>Submit readiness</h2>
              <span style={{ fontFamily: 'var(--font-mono)', color: pct === 100 ? '#10b981' : 'var(--accent)', fontWeight: 700 }}>
                {pct}%
              </span>
            </div>
            <div style={{ height: 8, background: 'var(--surface-input)', borderRadius: 4, margin: '12px 0 14px', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${pct}%`, background: pct === 100 ? '#10b981' : 'var(--accent)', borderRadius: 4 }} />
            </div>
            {(readiness?.checks || []).map(c => (
              <div key={c.id} style={{
                display: 'flex', gap: 10, alignItems: 'flex-start', padding: '8px 0',
                borderBottom: '1px solid var(--border)',
              }}>
                <span style={{ color: c.met ? '#10b981' : 'var(--text-dim)', fontSize: 14, width: 16 }}>{c.met ? '✓' : '○'}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, color: 'var(--text)', fontWeight: c.required ? 600 : 400 }}>
                    {c.label}{!c.required && <span style={{ color: 'var(--text-dim)', fontWeight: 400 }}> (optional)</span>}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-2)', marginTop: 2 }}>{c.detail}</div>
                </div>
              </div>
            ))}
            {readiness?.ready_to_submit ? (
              <button
                onClick={() => {
                  api.updatePublication(id!, { status: 'submitted' })
                    .then(() => { setNotice('Marked as submitted.'); qc.invalidateQueries({ queryKey: ['publication', id] }) })
                    .catch((e: Error) => setNotice(e.message))
                }}
                style={{ ...primaryBtn, width: '100%', marginTop: 14, justifyContent: 'center' }}
              >Mark ready → submit</button>
            ) : (
              <div style={{ ...muted, marginTop: 12 }}>
                Complete required checks before submit. Optional checks improve disclosure quality.
              </div>
            )}
          </section>

          <section style={{ ...card, marginTop: 16 }}>
            <h2 style={h2}>Submission compliance</h2>
            <p style={{ ...muted, marginTop: 0, marginBottom: 12 }}>
              These statements feed the readiness gate above. Journals ask for them at
              submission, and reviewers check them.
            </p>
            {COMPLIANCE_FIELDS.map(field => (
              <label key={field.key} style={{ display: 'block', marginBottom: 10 }}>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', color: 'var(--text-dim)' }}>
                  {field.label}
                </span>
                <textarea
                  rows={2}
                  value={compliance?.[field.key] ?? ''}
                  placeholder={field.placeholder}
                  onChange={e => setCompliance(c => ({ ...(c ?? {}), [field.key]: e.target.value }))}
                  style={{
                    width: '100%', boxSizing: 'border-box', marginTop: 4, padding: '6px 8px',
                    background: 'var(--surface-input)', border: '1px solid var(--border)',
                    borderRadius: 5, color: 'var(--text)', fontSize: 13, fontFamily: 'inherit',
                    resize: 'vertical',
                  }}
                />
              </label>
            ))}
            <button
              onClick={() => {
                if (!compliance) return
                api.updatePublication(id!, compliance as never)
                  .then(() => {
                    setNotice('Compliance statements saved.')
                    qc.invalidateQueries({ queryKey: ['publication', id] })
                    qc.invalidateQueries({ queryKey: ['paper-readiness', id] })
                  })
                  .catch((e: Error) => setNotice(e.message))
              }}
              style={{ ...primaryBtn, marginTop: 4 }}
            >Save statements</button>
          </section>

          <section style={{ ...card, marginTop: 16 }}>
            <h2 style={h2}>Open questions</h2>
            {openQuestions.length === 0 ? (
              <div style={muted}>No help flags in linked weekly updates.</div>
            ) : (
              openQuestions.map(q => (
                <div key={q.id} style={{
                  padding: '10px 12px', borderRadius: 8, marginBottom: 8,
                  background: 'rgba(var(--accent-rgb),0.08)', border: '1px solid rgba(var(--accent-rgb),0.25)',
                }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{q.item_title}</div>
                  {q.blocker && <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 4 }}>{q.blocker}</div>}
                  {q.what_changed && <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 4 }}>{q.what_changed}</div>}
                </div>
              ))
            )}
          </section>

          <section style={{ ...card, marginTop: 16 }}>
            <h2 style={h2}>AI disclosure</h2>
            <p style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.55, margin: 0 }}>
              {readiness?.ai_versions
                ? `${readiness.ai_versions} AI-generated version(s) are recorded with provenance (model + prompt hash). Human revisions: ${readiness.human_versions ?? 0}.`
                : 'No AI versions recorded yet. When you draft with AI, provenance is stored for integrity reporting.'}
            </p>
          </section>

          <div style={{ marginTop: 16 }}>
            <AiUsagePanel title="AI usage on this paper" publicationId={id} days={90} />
          </div>
        </aside>
      </div>
    </div>
  )
}

const COMPLIANCE_FIELDS = [
  { key: 'reporting_guideline', label: 'Reporting guideline', placeholder: 'STROBE / CONSORT / PRISMA / TRIPOD, or why none applies' },
  { key: 'data_availability', label: 'Data availability', placeholder: 'Where the data lives, or why it cannot be shared' },
  { key: 'code_availability', label: 'Code availability', placeholder: 'Repository and licence, or "not applicable"' },
  { key: 'conflict_of_interest', label: 'Conflict of interest', placeholder: 'Declare competing interests, or state that there are none' },
  { key: 'funding_statement', label: 'Funding', placeholder: 'Grant numbers and funders, or "no specific funding"' },
]

function ReadinessRing({ pct }: { pct: number }) {
  const r = 22
  const c = 2 * Math.PI * r
  const color = pct === 100 ? '#10b981' : '#ff8015'
  return (
    <div style={{ position: 'relative', width: 56, height: 56 }}>
      <svg width={56} height={56}>
        <circle cx={28} cy={28} r={r} fill="none" stroke="var(--border)" strokeWidth={5} />
        <circle
          cx={28} cy={28} r={r} fill="none" stroke={color} strokeWidth={5}
          strokeDasharray={c} strokeDashoffset={c * (1 - pct / 100)}
          strokeLinecap="round" transform="rotate(-90 28 28)"
        />
      </svg>
      <div style={{
        position: 'absolute', inset: 0, display: 'grid', placeItems: 'center',
        fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 700, color,
      }}>{pct}</div>
    </div>
  )
}

const card: React.CSSProperties = {
  background: 'var(--surface-panel)', border: '1px solid var(--border)',
  borderRadius: 12, padding: 18,
}
const h2: React.CSSProperties = { margin: '0 0 12px', fontSize: 15, color: 'var(--text-heading)' }
const label: React.CSSProperties = {
  fontSize: 11, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em',
  color: 'var(--text-dim)', marginBottom: 6, textTransform: 'uppercase',
}
const muted: React.CSSProperties = { fontSize: 12, color: 'var(--text-2)' }
const chip: React.CSSProperties = {
  padding: '5px 10px', borderRadius: 999, fontSize: 12, fontFamily: 'var(--font-mono)',
  border: '1px solid var(--border)', background: 'var(--surface-input)', color: 'var(--text-2)',
  cursor: 'pointer',
}
const select: React.CSSProperties = {
  width: '100%', padding: '8px 10px', fontSize: 13, fontFamily: 'var(--font-mono)',
  background: 'var(--surface-input)', border: '1px solid var(--border)',
  borderRadius: 6, color: 'var(--text)',
}
const primaryBtn: React.CSSProperties = {
  padding: '8px 14px', cursor: 'pointer', fontSize: 13, fontWeight: 700,
  background: 'var(--accent)', border: 'none', borderRadius: 8, color: '#1a1a1a',
  display: 'inline-flex', alignItems: 'center', gap: 6,
}
const ghostBtn: React.CSSProperties = {
  padding: '7px 12px', cursor: 'pointer', fontSize: 12,
  background: 'transparent', border: '1px solid var(--border)',
  borderRadius: 8, color: 'var(--text-2)',
}
