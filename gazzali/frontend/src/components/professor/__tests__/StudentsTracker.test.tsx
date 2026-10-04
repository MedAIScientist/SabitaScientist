import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { StudentsTracker } from '../StudentsTracker'
import { supervisionApi, type StudentOverview } from '../../../api'

vi.mock('../../../api', () => ({ supervisionApi: { studentsOverview: vi.fn() } }))

const row = (p: Partial<StudentOverview>): StudentOverview => ({
  student_id: 's', name: 'x', lab_name: 'Retina Lab', level: 'PhD', thesis_title: null, this_week: 'reviewed',
  last_submitted: null, weeks_submitted: 8, weeks_window: 8, risk: null, help_requested: null, awaiting_review: 0,
  followups_open: 0, followups_overdue: 0, tasks_open: 0, tasks_overdue: 0, blocked: [], active_papers: 0, attention: 0, reasons: [], ...p,
})

describe('StudentsTracker', () => {
  it('lists students who need attention first, with reasons in words', async () => {
    vi.mocked(supervisionApi.studentsOverview).mockResolvedValue([
      row({ student_id: 'a', name: 'melisa', this_week: 'submitted', attention: 6, awaiting_review: 1,
            reasons: ['asked for help', '1 blocked item'], help_requested: 'Need GPU time' }),
      row({ student_id: 'b', name: 'ali' }),
    ])
    render(<MemoryRouter><QueryClientProvider client={new QueryClient()}><StudentsTracker /></QueryClientProvider></MemoryRouter>)
    expect(await screen.findByText('1 needs your attention — they are listed first.')).toBeInTheDocument()
    const names = screen.getAllByRole('link').map(a => a.textContent)
    expect(names).toEqual(['melisa', 'ali'])
    expect(screen.getByText('asked for help')).toBeInTheDocument()
    expect(screen.getByText('“Need GPU time”')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Review update' })).toBeInTheDocument()
    expect(screen.getByText('On track')).toBeInTheDocument()
  })
})
