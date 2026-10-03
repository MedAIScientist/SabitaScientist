import { useQuery } from '@tanstack/react-query'
import { api } from '../../api'

/** How much of the shared AI quota is in use, and how many runs are going. */
export function UsageMeter() {
  const { data: u } = useQuery({ queryKey: ['research-usage'], queryFn: api.researchUsage, refetchInterval: 20_000 })
  if (!u) return null
  const pct = Math.min(100, Math.round((u.requests_last_minute / u.limit_per_minute) * 100))
  const busy = u.runs_running >= u.max_concurrent
  return (
    <div aria-label="AI usage" style={{ fontSize: 13, color: 'var(--text-3)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span>AI requests in the last minute (Gazzali)</span>
        <span>{u.requests_last_minute} / {u.limit_per_minute}</span>
      </div>
      <div style={{ height: 6, background: 'var(--border)', borderRadius: 3, margin: '4px 0 6px' }}>
        <div style={{ width: `${pct}%`, height: 6, borderRadius: 3, background: pct > 80 ? '#f43f5e' : 'var(--accent, #6366f1)' }} />
      </div>
      <div>
        AutoResearchClaw: {u.runs_running} running, {u.runs_waiting} waiting for a decision, {u.runs_queued} queued
        {busy && ' — a new run will wait in the queue.'}
      </div>
    </div>
  )
}
