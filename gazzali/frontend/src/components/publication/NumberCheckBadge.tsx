import type { NumberCheck } from '../../api'

/** Result of the verified-numbers check on an AI draft (paper §3.4). */
export function NumberCheckBadge({ check }: { check: NumberCheck | null | undefined }) {
  if (!check || check.checked === 0) return null
  const bad = check.unverified_in_results
  const title = check.recorded_values === 0
    ? 'No recorded results to check against yet'
    : check.examples.slice(0, 5).map(e => `${e.value}: …${e.context}…`).join('\n') || 'All numbers match recorded results'
  return (
    <span title={title} style={{
      marginLeft: 6, padding: '1px 7px', borderRadius: 4, fontSize: 12, fontWeight: 700,
      background: bad ? 'rgba(244,63,94,0.12)' : 'rgba(16,185,129,0.12)', color: bad ? '#f43f5e' : '#10b981',
    }}>
      {bad ? `${bad} unverified number${bad > 1 ? 's' : ''} in results` : `${check.verified}/${check.checked} numbers verified`}
    </span>
  )
}
