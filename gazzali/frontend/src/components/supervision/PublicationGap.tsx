import { Link } from 'react-router-dom'
import { PublicationGap as Gap } from '../../api'

function eta(gap: Gap, months: number | null): string {
  if (months === null) {
    return gap.months_observed === null
      ? 'No estimate: the journey has no start date.'
      : 'No estimate yet: nothing submitted since the journey began.'
  }
  const papers = Math.round((gap.pace_per_month ?? 0) * (gap.months_observed ?? 0))
  return `About ${months} month${months === 1 ? '' : 's'} at the current pace (${papers} submitted in ${gap.months_observed} months).`
}

/** Publication requirements still open: how many more, which drafts count toward them, and when. */
export function PublicationGap({ gap }: { gap?: Gap }) {
  if (!gap || gap.items.length === 0) return null
  return (
    <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
      {gap.items.map(item => (
        <div key={item.requirement} className="request">
          <div className="request-title">
            {item.requirement}: needs {item.gap} more
            <span className="hint" style={{ fontWeight: 400 }}> ({item.current} of {item.target})</span>
          </div>
          <div className="request-meta" style={{ marginTop: 2 }}>{eta(gap, item.eta_months)}</div>
          {item.in_progress.length > 0 ? (
            <ul style={{ margin: '8px 0 0 18px', fontSize: 13.5 }}>
              {item.in_progress.map(p => <li key={p.id}><Link to={`/publications/${p.id}`}>{p.title}</Link> <span className="hint">· {p.status}</span></li>)}
            </ul>
          ) : <p className="hint" style={{ marginTop: 6 }}>No drafts of this kind in progress.</p>}
        </div>
      ))}
    </div>
  )
}
