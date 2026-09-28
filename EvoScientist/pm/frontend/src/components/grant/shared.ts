import type { GrantStatus } from '../../api'

/** Status → accent colour, shared by the list, the detail header and the badges. */
export const STATUS_COLORS: Record<string, string> = {
  draft: '#6b7280',
  submitted: '#6366f1',
  under_review: '#f59e0b',
  awarded: '#10b981',
  rejected: '#f43f5e',
  active: '#22c55e',
  closed: '#6b7280',
}

export const CURRENCIES = ['TRY', 'USD', 'EUR', 'GBP', 'CHF']

export const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: '-created_at', label: 'newest first' },
  { value: 'created_at', label: 'oldest first' },
  { value: '-amount_awarded', label: 'largest award' },
  { value: 'amount_awarded', label: 'smallest award' },
  { value: 'end_date', label: 'ending soonest' },
  { value: '-end_date', label: 'ending latest' },
  { value: 'title', label: 'title A–Z' },
  { value: '-title', label: 'title Z–A' },
]

export function money(amount: number, currency: string): string {
  return `${amount.toLocaleString('en-US', { maximumFractionDigits: 2 })} ${currency}`
}

/** Collapse per-currency totals into one readable line. */
export function totalsLine(
  totals: { currency: string; awarded: number; requested: number }[],
  pick: 'awarded' | 'requested' = 'awarded'
): string {
  if (totals.length === 0) return '—'
  return totals
    .filter(t => t[pick] > 0)
    .map(t => money(t[pick], t.currency))
    .join(' · ') || '—'
}

export function todayISO(): string {
  return new Date().toISOString().slice(0, 10)
}

export function isOverdue(dueDate: string | null, completedAt: string | null): boolean {
  if (!dueDate || completedAt) return false
  return dueDate.slice(0, 10) < todayISO()
}

/** Days from today until an ISO date; negative when it already passed. */
export function daysUntil(iso: string | null): number | null {
  if (!iso) return null
  const target = new Date(`${iso.slice(0, 10)}T00:00:00Z`).getTime()
  if (Number.isNaN(target)) return null
  const today = new Date(`${todayISO()}T00:00:00Z`).getTime()
  return Math.round((target - today) / 86_400_000)
}

export type { GrantStatus }
