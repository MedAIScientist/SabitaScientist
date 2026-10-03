import { describe, it, expect } from 'vitest'
import type { Followup, WeeklyReport } from '../../../api'
import { attention, dueText, latestProgress, upcoming, weekState, weeklyHistory } from '../studentData'

const TODAY = new Date(2026, 9, 3) // Sat 3 Oct 2026
const rep = (p: Partial<WeeklyReport>): WeeklyReport => ({
  id: 'r', student_id: 's', week_start: '2026-09-28', status: 'draft', review_status: 'pending', risk_level: 'low', risk_override: null,
  accomplished: null, next_focus: null, support_requested: null, submitted_at: null, reviewed_at: null, reviewed_by: null,
  feedback: null, created_at: '', updated_at: '', items: [], ...p,
})
const fu = (p: Partial<Followup>): Followup => ({
  id: 'f', student_id: 's', professor_id: 'p', report_id: null, text: 'Send the ROC curves', due_date: null,
  status: 'open', student_note: null, created_at: '', closed_at: null, weeks_open: 1, overdue: false, ...p,
})
const task = (id: string, deadline: string | null) => ({ id, title: `T${id}`, status: 'todo', priority: 'medium', deadline, project_id: 'p1', project_name: 'DR' })

describe('studentData', () => {
  it('describes the week in plain words', () => {
    expect(weekState(undefined).cta).toBe('Start this week’s update')
    expect(weekState(rep({ items: [{} as never, {} as never] })).detail).toBe('2 items so far — not sent yet.')
    expect(weekState(rep({ status: 'submitted' })).label).toBe('Submitted')
    expect(weekState(rep({ status: 'submitted', reviewed_at: 'x', feedback: 'Good' })).cta).toBe('Read the feedback')
  })

  it('says how far a deadline is', () => {
    expect(dueText('2026-10-01', TODAY)).toEqual({ text: '2 days overdue', tone: 'bad' })
    expect(dueText('2026-10-04', TODAY).text).toBe('due tomorrow')
    expect(dueText('2026-10-20', TODAY).text).toBe('due Tue 20 Oct')
  })

  it('puts overdue things first and leaves calm items out', () => {
    const items = attention([task('1', '2026-10-05'), task('2', '2026-11-30')], [fu({ id: 'a', overdue: true })], undefined, TODAY)
    expect(items.map(i => i.key)).toEqual(['f-a', 't-1'])
  })

  it('lists the next 30 days soonest first', () => {
    const items = [{ id: 'i', kind: 'conference_paper', title: 'CWE paper', status: 'draft', stage: 'writing', link_path: '/x', deadline: '2026-10-18' }]
    const u = upcoming([task('1', '2026-10-07'), task('2', '2026-12-30')], items, [fu({ due_date: '2026-10-04' })], TODAY)
    expect(u.map(x => x.kind)).toEqual(['Supervisor request', 'Task', 'conference paper'])
  })

  it('takes the latest reported progress per item and shows missed weeks', () => {
    const reports = [
      rep({ week_start: '2026-09-21', status: 'submitted', items: [{ publication_id: 'pub1', progress_pct: 40 } as never] }),
      rep({ week_start: '2026-09-28', status: 'submitted', items: [{ publication_id: 'pub1', progress_pct: 55 } as never] }),
    ]
    expect(latestProgress(reports).get('pub1')).toBe(55)
    const h = weeklyHistory(reports, TODAY, 3)
    expect(h.map(x => [x.week, x.status])).toEqual([['2026-09-07', 'missed'], ['2026-09-14', 'missed'], ['2026-09-21', 'submitted']])
  })
})
