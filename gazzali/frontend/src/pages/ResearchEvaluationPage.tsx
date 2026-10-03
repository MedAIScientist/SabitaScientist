import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { stageTitle } from '../components/experiment/stageCatalog'

const pct = (v: number | null) => (v == null ? '—' : `${Math.round(v * 100)}%`)

/**
 * How AutoResearchClaw runs go in your labs: our measurements, not the paper's.
 * Gate approval rates hint where Gate-only mode would save time; nothing is skipped automatically.
 */
export function ResearchEvaluationPage() {
  const { data, error } = useQuery({ queryKey: ['research-evaluation'], queryFn: api.researchEvaluation })
  return (
    <div className="page" style={{ maxWidth: 1100, margin: '0 auto', padding: '28px' }}>
      <h1 className="page-title">Research runs: evaluation</h1>
      {error && <div className="msg msg-error" role="alert">{(error as Error).message}</div>}
      {data && (
        <>
          <dl style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
            <div><dt>Runs</dt><dd>{data.summary.runs}</dd></div>
            <div><dt>Finished</dt><dd>{data.summary.finished}</dd></div>
            <div><dt>Completion</dt><dd>{pct(data.summary.completion_rate)}</dd></div>
            <div><dt>Decisions per run</dt><dd>{data.summary.mean_interventions ?? '—'}</dd></div>
            <div><dt>PI quality (1–10)</dt><dd>{data.summary.mean_pi_quality ?? '—'}</dd></div>
          </dl>
          <h3 className="section-title">Gates</h3>
          {data.gates.length === 0 ? <p>No gate decisions yet.</p> : (
            <table style={{ width: '100%', fontSize: 14, borderCollapse: 'collapse' }}>
              <thead><tr><th align="left">Stage</th><th align="right">Approved</th><th align="right">Redirected</th><th align="right">Approve rate</th><th align="left">Hint</th></tr></thead>
              <tbody>{data.gates.map(g => (
                <tr key={g.stage}><td>{g.stage}. {stageTitle(g.stage)}</td><td align="right">{g.approved}</td><td align="right">{g.redirected}</td>
                  <td align="right">{pct(g.approve_rate)}</td><td>{g.advice}</td></tr>
              ))}</tbody>
            </table>
          )}
          <h3 className="section-title" style={{ marginTop: 20 }}>Runs</h3>
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead><tr><th align="left">Started</th><th align="left">Question</th><th align="left">Status</th><th align="right">Decisions</th>
              <th align="right">Refines</th><th align="right">Pivots</th><th align="right">Retries</th><th align="right">Unverified in paper</th><th align="right">PI score</th></tr></thead>
            <tbody>{data.runs.map(r => (
              <tr key={r.id}>
                <td>{new Date(r.created_at).toLocaleDateString()}</td><td>{r.topic.slice(0, 70)}</td>
                <td>{r.status}{r.stage ? ` (${r.stage}/23)` : ''}</td><td align="right">{r.interventions}</td>
                <td align="right">{r.refines ?? '—'}</td><td align="right">{r.pivots ?? '—'}</td><td align="right">{r.retries ?? '—'}</td>
                <td align="right">{r.unverified_in_paper ?? '—'}</td><td align="right">{r.pi_quality ?? '—'}</td>
              </tr>
            ))}</tbody>
          </table>
        </>
      )}
    </div>
  )
}
