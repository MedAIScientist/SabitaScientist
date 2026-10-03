import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { WeeklyUpdatePage } from '../WeeklyUpdatePage'
import { mondayOf, ymd } from '../../components/supervision/WeekPicker'

const { weekReport, currentWeekReport, listReports, weeklyTasks } = vi.hoisted(() => ({
  weekReport: vi.fn(),
  currentWeekReport: vi.fn(),
  listReports: vi.fn(),
  weeklyTasks: vi.fn(),
}))

vi.mock('../../api', () => ({
  api: {},
  supervisionApi: {
    weekReport, currentWeekReport, listReports, weeklyTasks,
    updateSummary: vi.fn(), upsertItem: vi.fn(), submitReport: vi.fn(),
  },
}))
vi.mock('../../auth', () => ({ useAuth: () => ({ role: 'student', isAdmin: false }) }))
vi.mock('../../components/supervision/Followups', () => ({ StudentFollowups: () => null }))

const THIS_WEEK = ymd(mondayOf(new Date()))

function weekOf(offset: number): string {
  const d = mondayOf(new Date())
  d.setDate(d.getDate() + offset * 7)
  return ymd(d)
}

const REPORT = (week: string, extra: Record<string, unknown> = {}) => ({
  id: `r-${week}`, student_id: 's', week_start: week, status: 'draft', review_status: 'pending',
  risk_level: 'low', risk_override: null, accomplished: null, next_focus: null,
  support_requested: null, submitted_at: null, reviewed_at: null, reviewed_by: null,
  feedback: null, created_at: '', updated_at: '', items: [], ...extra,
})

function wrap(initial = '/weekly-update') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route path="/weekly-update" element={<WeeklyUpdatePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('weekly update calendar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listReports.mockResolvedValue([])
    weeklyTasks.mockResolvedValue({ week_start: THIS_WEEK, report_id: null, report_status: null, tasks: [] })
    currentWeekReport.mockResolvedValue(REPORT(THIS_WEEK))
    weekReport.mockResolvedValue(null)
  })

  it('offers the same calendar professors get, plus the student’s own week list', async () => {
    listReports.mockResolvedValue([REPORT(THIS_WEEK), REPORT(weekOf(-1), { status: 'submitted' })])
    wrap()

    expect(await screen.findByRole('grid', { name: /Pick a week/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: new RegExp(`Week of ${THIS_WEEK}`) })).toBeInTheDocument()
    expect(await screen.findByText(weekOf(-1))).toBeInTheDocument()
    expect(screen.getByText('submitted')).toBeInTheDocument()
  })

  it('opens the current week for writing without being asked', async () => {
    wrap()
    await waitFor(() => expect(currentWeekReport).toHaveBeenCalledWith(THIS_WEEK))
    expect(weekReport).not.toHaveBeenCalled()
  })

  it('shows an empty week as empty instead of creating a draft', async () => {
    weekReport.mockResolvedValue(null)
    wrap(`/weekly-update?week=${weekOf(-3)}`)

    expect(await screen.findByText(new RegExp(`No update was written for the week of ${weekOf(-3)}`))).toBeInTheDocument()
    // Browsing must not touch the write endpoint at all.
    expect(currentWeekReport).not.toHaveBeenCalled()
    expect(weekReport).toHaveBeenCalledWith(weekOf(-3))
  })

  it('starts a past week only when the student chooses to write it', async () => {
    weekReport.mockResolvedValue(null)
    currentWeekReport.mockResolvedValue(REPORT(weekOf(-3)))
    wrap(`/weekly-update?week=${weekOf(-3)}`)

    fireEvent.click(await screen.findByRole('button', { name: /Write this week’s update/ }))

    await waitFor(() => expect(currentWeekReport).toHaveBeenCalledWith(weekOf(-3)))
  })

  it('reads back a week that was written, with its feedback', async () => {
    weekReport.mockResolvedValue(REPORT(weekOf(-1), {
      status: 'submitted', reviewed_at: '2026-09-30', feedback: 'Good progress, narrow the scope.',
      accomplished: 'Finished the cohort split',
      items: [{ id: 'i1', report_id: 'r', task_id: null, publication_id: null, experiment_id: null, item_title: 'Denoise', item_kind: 'task', progress_pct: 100, status: 'done', blocker: null, needs_help: false, what_changed: null, next_step: null, risk_level: 'low', next_deadline: null, sort_order: 0 }],
    }))
    wrap(`/weekly-update?week=${weekOf(-1)}`)

    expect(await screen.findByText('Good progress, narrow the scope.')).toBeInTheDocument()
    expect(screen.getByText('Finished the cohort split')).toBeInTheDocument()
    expect(screen.getByText('Denoise')).toBeInTheDocument()
    // A submitted week is a record: no edit affordance.
    expect(screen.queryByRole('button', { name: /Edit this week’s update/ })).not.toBeInTheDocument()
  })

  it('lets a draft week be reopened for editing', async () => {
    weekReport.mockResolvedValue(REPORT(weekOf(-2)))
    currentWeekReport.mockResolvedValue(REPORT(weekOf(-2)))
    wrap(`/weekly-update?week=${weekOf(-2)}`)

    fireEvent.click(await screen.findByRole('button', { name: /Edit this week’s update/ }))
    await waitFor(() => expect(currentWeekReport).toHaveBeenCalledWith(weekOf(-2)))
  })

  it('moves a week at a time with the arrows', async () => {
    wrap()
    await screen.findByRole('grid', { name: /Pick a week/i })

    fireEvent.click(screen.getByRole('button', { name: /Previous week/ }))

    await waitFor(() => expect(weekReport).toHaveBeenCalledWith(weekOf(-1)))
  })

  it('does not let the student walk into the future', async () => {
    wrap()
    await screen.findByRole('grid', { name: /Pick a week/i })
    expect(screen.getByRole('button', { name: /Next week/ })).toBeDisabled()
  })

  it('jumps to the week of any day the student clicks', async () => {
    wrap()
    const grid = await screen.findByRole('grid', { name: /Pick a week/i })
    const weekButtons = grid.querySelectorAll('button')
    expect(weekButtons.length).toBeGreaterThan(1)

    fireEvent.click(weekButtons[0])

    await waitFor(() => expect(weekReport.mock.calls.length + currentWeekReport.mock.calls.length).toBeGreaterThan(0))
  })
})
