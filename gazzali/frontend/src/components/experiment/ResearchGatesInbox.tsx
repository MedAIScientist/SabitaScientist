import { useQuery } from '@tanstack/react-query'
import { api } from '../../api'
import { ResearchGateCard } from './ResearchGateCard'

/**
 * AutoResearchClaw gates waiting on the signed-in user. Renders nothing when
 * there is nothing to decide, so it can sit on any dashboard.
 */
export function ResearchGatesInbox() {
  const { data: gates = [] } = useQuery({ queryKey: ['research-gates'], queryFn: api.researchGates, refetchInterval: 60_000 })
  if (gates.length === 0) return null
  return (
    <section aria-label="Research gates" style={{ margin: '0 0 26px' }}>
      <h3 className="section-title">Research gates <span className="count">{gates.length}</span></h3>
      <div className="inbox-grid">
        {gates.map(g => <ResearchGateCard key={g.id} run={g} />)}
      </div>
    </section>
  )
}
