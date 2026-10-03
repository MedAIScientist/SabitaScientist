import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { StudentDashboard } from '../StudentDashboard'

const { weeklyTasks, updateWeeklyTask } = vi.hoisted(() => ({
  weeklyTasks: vi.fn(),
  updateWeeklyTask: vi.fn(),
}))

vi.mock('../../../api', () => ({
  api: { myTasks: vi.fn().mockResolvedValue([]) },
  supervisionApi: {
    listReports: vi.fn().mockResolvedValue([]),
    listFollowups: vi.fn().mockResolvedValue([]),
    researchItems: vi.fn().mockResolvedValue([]),
    mySupervisor: vi.fn().mockResolvedValue(null),
    readiness: vi.fn().mockResolvedValue(null),
    getMeetingSetting: vi.fn().mockResolvedValue(null),
    weeklyTasks,
    updateWeeklyTask,
  },
}))

vi.mock('../../experiment/ResearchGatesInbox', () => ({ ResearchGatesInbox: () => null }))

const TASK = {
  id: 't1', title: 'Denoise the cohort', status: 'todo', priority: 'high',
  deadline: null, project_id: 'p1', project_name: 'Alzheimer imaging',
  item_id: null, item_status: null, item_progress_pct: null,
  item_needs_help: null, report_id: null, report_status: null,
}

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <StudentDashboard username="stud" />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('student dashboard tasks', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    updateWeeklyTask.mockResolvedValue({ task: { ...TASK, status: 'done' }, report_locked: false })
  })

  it('lists the week’s assigned tasks', async () => {
    weeklyTasks.mockResolvedValue({ week_start: '2026-09-28', report_id: null, report_status: null, tasks: [TASK] })
    wrap()
    expect(await screen.findByText('Denoise the cohort')).toBeInTheDocument()
    expect(screen.getByText(/Alzheimer imaging/)).toBeInTheDocument()
  })

  it('says so when nothing is assigned', async () => {
    weeklyTasks.mockResolvedValue({ week_start: '2026-09-28', report_id: null, report_status: null, tasks: [] })
    wrap()
    expect(await screen.findByText(/No tasks assigned to you this week/)).toBeInTheDocument()
  })

  it('moves the task and therefore the weekly update in one action', async () => {
    weeklyTasks.mockResolvedValue({ week_start: '2026-09-28', report_id: 'r1', report_status: 'draft', tasks: [TASK] })
    wrap()
    await screen.findByText('Denoise the cohort')

    fireEvent.click(screen.getByRole('button', { name: 'Done' }))

    await waitFor(() => expect(updateWeeklyTask).toHaveBeenCalledTimes(1))
    expect(updateWeeklyTask).toHaveBeenCalledWith('t1', { status: 'done' }, expect.any(String))
  })

  it('marks the tasks already listed in this week’s update', async () => {
    weeklyTasks.mockResolvedValue({
      week_start: '2026-09-28', report_id: 'r1', report_status: 'draft',
      tasks: [{ ...TASK, item_id: 'i1', item_status: 'planned' }],
    })
    wrap()
    expect(await screen.findByText('✓ in update')).toBeInTheDocument()
  })

  it('explains that a submitted week will not be rewritten', async () => {
    weeklyTasks.mockResolvedValue({ week_start: '2026-09-28', report_id: 'r1', report_status: 'submitted', tasks: [TASK] })
    updateWeeklyTask.mockResolvedValue({ task: TASK, report_locked: true })
    wrap()
    await screen.findByText('Denoise the cohort')

    fireEvent.click(screen.getByRole('button', { name: 'Doing' }))

    expect(await screen.findByRole('status')).toHaveTextContent(/already submitted/i)
  })

  it('raises a help flag without moving the task', async () => {
    weeklyTasks.mockResolvedValue({ week_start: '2026-09-28', report_id: 'r1', report_status: 'draft', tasks: [TASK] })
    wrap()
    await screen.findByText('Denoise the cohort')

    fireEvent.click(screen.getByRole('button', { name: /Needs help/ }))

    await waitFor(() => expect(updateWeeklyTask).toHaveBeenCalledWith('t1', { needs_help: true }, expect.any(String)))
  })

  it('reports a failure instead of pretending the task moved', async () => {
    weeklyTasks.mockResolvedValue({ week_start: '2026-09-28', report_id: 'r1', report_status: 'draft', tasks: [TASK] })
    updateWeeklyTask.mockRejectedValue(new Error('This task is not assigned to you'))
    wrap()
    await screen.findByText('Denoise the cohort')

    fireEvent.click(screen.getByRole('button', { name: 'Done' }))

    expect(await screen.findByRole('status')).toHaveTextContent(/not assigned to you/i)
  })
})
