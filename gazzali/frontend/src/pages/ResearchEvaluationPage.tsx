import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { stageTitle } from '../components/experiment/stageCatalog'

const pct = (v: number | null) => (v == null ? '—' : `${Math.round(v * 100)}%`)

/**
 * Research quality & integrity dashboard — four blocks:
 * 1 Run quality  2 Gate economics  3 Paper-bound integrity  4 Outcomes
 */
export function ResearchEvaluationPage() {
  const navigate = useNavigate()
  const { data, error, isLoading } = useQuery({
    queryKey: ['research-evaluation'],
    queryFn: api.researchEvaluation,
  })

  return (
    <div className="page" style={{ maxWidth: 1100, margin: '0 auto', padding: '28px' }}>
      <h1 className="page-title">Research quality & integrity</h1>
      <p style={{ color: 'var(--text-2)', fontSize: 14, marginTop: -6, marginBottom: 22 }}>
        How AutoResearchClaw runs go in your labs — quality, human gates, paper integrity, and outcomes.
        Measured on this platform, not taken from the ARC paper.
      </p>

      {error && <div className="msg msg-error" role="alert">{(error as Error).message}</div>}
      {isLoading && <p style={{ color: 'var(--text-2)' }}>Loading evaluation…</p>}

      {data && (
        <>
          {/* Summary strip */}
          <dl style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))',
            gap: 12, marginBottom: 28,
          }}>
            <Stat label="Runs" value={data.summary.runs} />
            <Stat label="Finished" value={data.summary.finished} />
            <Stat label="Completion" value={pct(data.summary.completion_rate)} />
            <Stat label="Decisions / run" value={data.summary.mean_interventions ?? '—'} />
            <Stat label="PI quality (1–10)" value={data.summary.mean_pi_quality ?? '—'} />
            <Stat label="Papers from runs" value={data.outcomes.runs_with_publication} />
          </dl>

          {/* 1. Run quality */}
          <Section
            title="1 · Run quality"
            subtitle="Completion, PI score, and self-healing (refines / pivots / retries) over recent runs"
          >
            {data.quality_trend.length === 0 ? (
              <Empty text="No runs yet." />
            ) : (
              <>
                <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 100, marginBottom: 16 }}>
                  {data.quality_trend.map(t => {
                    const q = t.pi_quality ?? 0
                    return (
                      <div key={t.id} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                        <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>
                          {t.pi_quality != null ? t.pi_quality : '—'}
                        </div>
                        <div style={{
                          width: '100%', borderRadius: '4px 4px 0 0',
                          height: Math.max(4, (q / 10) * 70),
                          background: t.status === 'done' ? '#10b981' : t.status === 'failed' ? '#f43f5e' : '#ff8015',
                        }} />
                        <div style={{ fontSize: 9, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                          {new Date(t.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                        </div>
                      </div>
                    )
                  })}
                </div>
                <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      {['Started', 'Status', 'PI', 'Decisions', 'Refines', 'Pivots', 'Retries'].map(h => (
                        <th key={h} align={h === 'Started' || h === 'Status' ? 'left' : 'right'}
                          style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)', color: 'var(--text-dim)', fontSize: 11 }}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.quality_trend.map(t => (
                      <tr key={t.id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: '6px 8px' }}>{new Date(t.created_at).toLocaleDateString()}</td>
                        <td style={{ padding: '6px 8px' }}>{t.status}</td>
                        <td align="right" style={{ padding: '6px 8px' }}>{t.pi_quality ?? '—'}</td>
                        <td align="right" style={{ padding: '6px 8px' }}>{t.interventions}</td>
                        <td align="right" style={{ padding: '6px 8px' }}>{t.refines ?? '—'}</td>
                        <td align="right" style={{ padding: '6px 8px' }}>{t.pivots ?? '—'}</td>
                        <td align="right" style={{ padding: '6px 8px' }}>{t.retries ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </Section>

          {/* 2. Gate economics */}
          <Section
            title="2 · Gate economics"
            subtitle="Where humans intervene most, and which gates are nearly always approved (SmartPause hints — nothing is skipped automatically)"
          >
            <h4 style={{ fontSize: 13, color: 'var(--text-heading)', margin: '0 0 8px' }}>
              Intervention hotspots
            </h4>
            {data.gate_economics.top_intervention_stages.length === 0 ? (
              <Empty text="No redirected decisions yet." />
            ) : (
              <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse', marginBottom: 18 }}>
                <thead>
                  <tr>
                    {['Stage', 'Redirected', 'Total', 'Approve rate'].map((h, i) => (
                      <th key={h} align={i === 0 ? 'left' : 'right'}
                        style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)', color: 'var(--text-dim)', fontSize: 11 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.gate_economics.top_intervention_stages.map(g => (
                    <tr key={g.stage} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '6px 8px' }}>{g.stage}. {stageTitle(g.stage)}</td>
                      <td align="right" style={{ padding: '6px 8px', color: '#f59e0b', fontWeight: 600 }}>{g.redirected}</td>
                      <td align="right" style={{ padding: '6px 8px' }}>{g.total}</td>
                      <td align="right" style={{ padding: '6px 8px' }}>{pct(g.approve_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <h4 style={{ fontSize: 13, color: 'var(--text-heading)', margin: '0 0 8px' }}>
              Auto-approve candidates (≥{data.gate_economics.min_decisions_for_advice} decisions, ≥90% approved)
            </h4>
            {data.gate_economics.auto_approve_candidates.length === 0 ? (
              <Empty text="No gate is stable enough yet to skip safely." />
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {data.gate_economics.auto_approve_candidates.map(g => (
                  <span key={g.stage} style={{
                    padding: '6px 12px', borderRadius: 999, fontSize: 12,
                    background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.35)',
                    color: '#10b981', fontFamily: 'var(--font-mono)',
                  }}>
                    {g.stage}. {g.stage_name || stageTitle(g.stage)} · {pct(g.approve_rate)}
                  </span>
                ))}
              </div>
            )}

            <h4 style={{ fontSize: 13, color: 'var(--text-heading)', margin: '18px 0 8px' }}>All gates</h4>
            {data.gates.length === 0 ? (
              <Empty text="No gate decisions yet." />
            ) : (
              <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Stage', 'Approved', 'Redirected', 'Rate', 'Advice'].map((h, i) => (
                      <th key={h} align={i === 0 || i === 4 ? 'left' : 'right'}
                        style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)', color: 'var(--text-dim)', fontSize: 11 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.gates.map(g => (
                    <tr key={g.stage} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '6px 8px' }}>{g.stage}. {stageTitle(g.stage)}</td>
                      <td align="right" style={{ padding: '6px 8px' }}>{g.approved}</td>
                      <td align="right" style={{ padding: '6px 8px' }}>{g.redirected}</td>
                      <td align="right" style={{ padding: '6px 8px' }}>{pct(g.approve_rate)}</td>
                      <td style={{ padding: '6px 8px', color: 'var(--text-2)', fontSize: 12 }}>{g.advice}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Section>

          {/* 3. Paper-bound integrity */}
          <Section
            title="3 · Paper-bound integrity"
            subtitle="Unverified numbers and integrity checks on papers produced from research runs"
          >
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
              <Stat label="Papers tracked" value={data.integrity.papers_tracked} />
              <Stat label="With unverified numbers" value={data.integrity.papers_with_unverified_data}
                accent={data.integrity.papers_with_unverified_data > 0} />
              <Stat label="Unverified total" value={data.integrity.unverified_total}
                accent={data.integrity.unverified_total > 0} />
            </div>
            {data.integrity.papers.length === 0 ? (
              <Empty text="No research run is linked to a publication yet." />
            ) : (
              <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Paper', 'Status', 'Unverified in results', 'Integrity run'].map((h, i) => (
                      <th key={h} align={i === 0 ? 'left' : 'right'}
                        style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)', color: 'var(--text-dim)', fontSize: 11 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.integrity.papers.map(p => (
                    <tr key={p.publication_id} style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }}
                      onClick={() => navigate(`/publications/${p.publication_id}/studio`)}>
                      <td style={{ padding: '6px 8px', color: 'var(--text)' }}>{p.title || p.publication_id}</td>
                      <td align="right" style={{ padding: '6px 8px' }}>{p.pub_status || '—'}</td>
                      <td align="right" style={{
                        padding: '6px 8px',
                        color: p.unverified_in_results ? '#f43f5e' : 'var(--text-2)',
                        fontWeight: p.unverified_in_results ? 600 : 400,
                      }}>
                        {p.unverified_in_results ?? '—'}
                      </td>
                      <td align="right" style={{
                        padding: '6px 8px',
                        color: p.integrity_passed == null ? 'var(--text-2)' : p.integrity_passed ? '#10b981' : '#f59e0b',
                      }}>
                        {p.integrity_passed == null ? 'not run' : p.integrity_passed ? 'passed' : 'failed'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Section>

          {/* 4. Outcomes */}
          <Section
            title="4 · Outcomes"
            subtitle="Did runs produce papers and measured metrics — not just ‘finished’"
          >
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <Stat label="Finished with paper" value={data.outcomes.finished_with_paper} accent />
              <Stat label="Runs with publication" value={data.outcomes.runs_with_publication} />
              <Stat label="Runs with metric" value={data.outcomes.runs_with_metric} />
              <Stat label="Mean primary metric"
                value={data.outcomes.mean_primary_metric != null ? String(data.outcomes.mean_primary_metric) : '—'} />
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 14, lineHeight: 1.55 }}>
              Click a paper row in §3 to open its Paper Studio (evidence pack, claims, integrity).
              Gate hints never skip a decision — they only show where human review is rarely changing the path.
            </p>
          </Section>

          {/* Run table (detail) */}
          <Section title="All runs" subtitle="Operational detail — decisions, self-healing, PI score">
            {data.runs.length === 0 ? (
              <Empty text="No runs yet." />
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      {['Started', 'Question', 'Status', 'Decisions', 'Refines', 'Pivots', 'Retries', 'Unverified', 'PI'].map(h => (
                        <th key={h} align={['Started', 'Question', 'Status'].includes(h) ? 'left' : 'right'}
                          style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)', color: 'var(--text-dim)', fontSize: 10, whiteSpace: 'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.runs.map(r => (
                      <tr key={r.id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: '6px 8px', whiteSpace: 'nowrap' }}>{new Date(r.created_at).toLocaleDateString()}</td>
                        <td style={{ padding: '6px 8px', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.topic}</td>
                        <td style={{ padding: '6px 8px', whiteSpace: 'nowrap' }}>{r.status}{r.stage ? ` (${r.stage}/23)` : ''}</td>
                        <td align="right" style={{ padding: '6px 8px' }}>{r.interventions}</td>
                        <td align="right" style={{ padding: '6px 8px' }}>{r.refines ?? '—'}</td>
                        <td align="right" style={{ padding: '6px 8px' }}>{r.pivots ?? '—'}</td>
                        <td align="right" style={{ padding: '6px 8px' }}>{r.retries ?? '—'}</td>
                        <td align="right" style={{ padding: '6px 8px', color: r.unverified_in_paper ? '#f43f5e' : undefined }}>
                          {r.unverified_in_paper ?? '—'}
                        </td>
                        <td align="right" style={{ padding: '6px 8px' }}>{r.pi_quality ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>
        </>
      )}
    </div>
  )
}

function Section({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <section style={{
      background: 'var(--surface-panel)', border: '1px solid var(--border)',
      borderRadius: 12, padding: 18, marginBottom: 18,
    }}>
      <h2 style={{ margin: '0 0 4px', fontSize: 16, color: 'var(--text-heading)' }}>{title}</h2>
      <p style={{ margin: '0 0 14px', fontSize: 12, color: 'var(--text-2)', lineHeight: 1.5 }}>{subtitle}</p>
      {children}
    </section>
  )
}

function Stat({ label, value, accent }: { label: string; value: React.ReactNode; accent?: boolean }) {
  return (
    <div style={{
      padding: '12px 14px', borderRadius: 10,
      background: 'var(--surface-input)', border: '1px solid var(--border)',
    }}>
      <div style={{
        fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em',
        color: 'var(--text-dim)', marginBottom: 6, textTransform: 'uppercase',
      }}>{label}</div>
      <div style={{
        fontSize: 22, fontWeight: 700, fontFamily: 'var(--font-mono)',
        color: accent ? '#ff8015' : 'var(--text-heading)',
      }}>{value}</div>
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return <div style={{ padding: '12px 0', color: 'var(--text-2)', fontSize: 13 }}>{text}</div>
}
