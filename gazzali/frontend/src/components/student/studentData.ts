// Pure helpers behind the student dashboard (no fetching, easy to test).
import type { Followup, MeetingSetting, WeeklyReport } from '../../api'
import { mondayOf, ymd } from '../supervision/WeekPicker'

export interface MyTask { id: string; title: string; status: string; priority: string; deadline: string | null; project_id: string; project_name: string }
export interface MyItem { id: string; kind: string; title: string; status: string; stage: string; link_path: string; deadline?: string | null }

export type Tone = 'neutral' | 'good' | 'warn' | 'bad'
export interface WeekState { label: string; detail: string; cta: string; tone: Tone }

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

export function thisMonday(today = new Date()): string {
  return ymd(mondayOf(today))
}

export function currentReport(reports: WeeklyReport[], monday: string): WeeklyReport | undefined {
  return reports.find(r => r.week_start === monday)
}

/** What this week's update needs, in the student's words. */
export function weekState(report: WeeklyReport | undefined): WeekState {
  if (!report) return { label: 'Not started', detail: 'Tell your supervisor what you did this week.', cta: 'Start this week’s update', tone: 'warn' }
  if (report.status !== 'submitted') {
    const n = report.items?.length ?? 0
    return { label: 'Draft', detail: `${n} item${n === 1 ? '' : 's'} so far — not sent yet.`, cta: 'Finish and submit', tone: 'warn' }
  }
  if (report.review_status === 'reviewed' || report.reviewed_at) {
    return report.feedback
      ? { label: 'Reviewed', detail: 'Your supervisor left feedback.', cta: 'Read the feedback', tone: 'good' }
      : { label: 'Reviewed', detail: 'Your supervisor has seen it.', cta: 'Open this week', tone: 'good' }
  }
  return { label: 'Submitted', detail: 'Waiting for your supervisor’s review.', cta: 'Open this week', tone: 'good' }
}

export function meetingText(m: MeetingSetting | null | undefined): string | null {
  if (!m) return null
  return `${WEEKDAYS[m.weekday] ?? ''}${m.time_local ? ` ${m.time_local}` : ''}`.trim() || null
}

/** "Mon 5 Oct" (or "5 Oct"), from a local YYYY-MM-DD. */
export function shortDate(iso: string, weekday = true): string {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-GB', { ...(weekday ? { weekday: 'short' } : {}), day: 'numeric', month: 'short' })
}

function daysUntil(date: string, today: Date): number {
  const [y, mo, d] = date.slice(0, 10).split('-').map(Number)
  const t = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  return Math.round((new Date(y, mo - 1, d).getTime() - t.getTime()) / 86_400_000)
}

export function dueText(date: string | null | undefined, today = new Date()): { text: string; tone: Tone } {
  if (!date) return { text: 'no deadline', tone: 'neutral' }
  const n = daysUntil(date, today)
  if (n < 0) return { text: `${-n} day${n === -1 ? '' : 's'} overdue`, tone: 'bad' }
  if (n === 0) return { text: 'due today', tone: 'warn' }
  if (n === 1) return { text: 'due tomorrow', tone: 'warn' }
  return { text: n <= 7 ? `due in ${n} days` : `due ${shortDate(date)}`, tone: n <= 3 ? 'warn' : 'neutral' }
}

export interface AttentionItem { key: string; text: string; detail: string; path: string; tone: Tone }

/** The few things that need the student now; empty means nothing urgent. */
export function attention(tasks: MyTask[], followups: Followup[], report: WeeklyReport | undefined, today = new Date()): AttentionItem[] {
  const out: AttentionItem[] = []
  for (const f of followups.filter(f => f.status === 'open')) {
    if (f.overdue || (f.due_date && daysUntil(f.due_date, today) <= 3)) {
      out.push({ key: `f-${f.id}`, text: f.text, detail: `Asked by your supervisor · ${dueText(f.due_date, today).text}`, path: '/weekly-update', tone: f.overdue ? 'bad' : 'warn' })
    }
  }
  for (const t of tasks) {
    if (t.deadline && daysUntil(t.deadline, today) <= 3) {
      const d = dueText(t.deadline, today)
      out.push({ key: `t-${t.id}`, text: t.title, detail: `${t.project_name} · ${d.text}`, path: `/projects/${t.project_id}`, tone: d.tone })
    }
  }
  if (report?.feedback && report.status === 'submitted') {
    out.push({ key: 'feedback', text: 'Feedback on this week’s update', detail: report.feedback.slice(0, 90), path: '/weekly-update', tone: 'neutral' })
  }
  const rank = { bad: 0, warn: 1, neutral: 2, good: 3 }
  return out.sort((a, b) => rank[a.tone] - rank[b.tone])
}

export interface UpcomingItem { date: string; kind: string; title: string; path: string }

/** Deadlines in the next ``days`` days, soonest first. */
export function upcoming(tasks: MyTask[], items: MyItem[], followups: Followup[], today = new Date(), days = 30): UpcomingItem[] {
  const inRange = (d?: string | null) => !!d && daysUntil(d, today) >= 0 && daysUntil(d, today) <= days
  const out: UpcomingItem[] = [
    ...tasks.filter(t => inRange(t.deadline)).map(t => ({ date: t.deadline!.slice(0, 10), kind: 'Task', title: t.title, path: `/projects/${t.project_id}` })),
    ...items.filter(i => inRange(i.deadline)).map(i => ({ date: i.deadline!.slice(0, 10), kind: i.kind.replace(/_/g, ' '), title: i.title, path: i.link_path })),
    ...followups.filter(f => f.status === 'open' && inRange(f.due_date)).map(f => ({ date: f.due_date!.slice(0, 10), kind: 'Supervisor request', title: f.text, path: '/weekly-update' })),
  ]
  return out.sort((a, b) => a.date.localeCompare(b.date))
}

/** Latest reported progress (%) per research item, from the weekly updates. */
export function latestProgress(reports: WeeklyReport[]): Map<string, number> {
  const out = new Map<string, number>()
  for (const r of [...reports].sort((a, b) => b.week_start.localeCompare(a.week_start))) {
    for (const it of r.items ?? []) {
      for (const key of [it.publication_id, it.experiment_id, it.item_title?.toLowerCase()]) {
        if (key && !out.has(key)) out.set(key, it.progress_pct)
      }
    }
  }
  return out
}

export interface WeekCell { week: string; status: 'submitted' | 'draft' | 'missed' }

/** The last ``n`` weeks before this one, oldest first. */
export function weeklyHistory(reports: WeeklyReport[], today = new Date(), n = 8): WeekCell[] {
  const monday = mondayOf(today)
  return Array.from({ length: n }, (_, i) => {
    const d = new Date(monday)
    d.setDate(monday.getDate() - 7 * (n - i))
    const week = ymd(d)
    const r = reports.find(x => x.week_start === week)
    return { week, status: r ? (r.status === 'submitted' ? 'submitted' : 'draft') : 'missed' }
  })
}
