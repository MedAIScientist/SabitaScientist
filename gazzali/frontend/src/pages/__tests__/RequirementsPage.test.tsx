import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RequirementsPage } from '../RequirementsPage'
import { supervisionApi } from '../../api'

vi.mock('../../auth', () => ({ useAuth: () => ({ isAdmin: false, role: 'professor' }) }))
vi.mock('../../api', () => ({
  supervisionApi: { listRequirements: vi.fn(), createRequirement: vi.fn(), archiveRequirement: vi.fn(), myStudents: vi.fn() },
}))

const wrap = (ui: React.ReactNode) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>
const base = { description: null, req_type: 'research_item', research_item_type: 'Journal Paper', min_stage: null, unit: 'papers', required: true, active: true, created_at: '' }

describe('RequirementsPage (professor)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(supervisionApi.myStudents).mockResolvedValue([{ id: 'a', student_id: 's1', student_name: 'melisa', professor_id: 'p', active_from: '', active_until: null, created_at: '' }])
    vi.mocked(supervisionApi.listRequirements).mockResolvedValue([
      { ...base, id: 'r1', level: 'PhD', title: 'Two journal papers', target_value: 2, professor_id: 'p', student_id: null },
      { ...base, id: 'r2', level: 'PhD', title: 'Ethics course', target_value: 1, professor_id: null, student_id: null },
    ])
    vi.mocked(supervisionApi.createRequirement).mockResolvedValue({ ...base, id: 'r3', level: 'PhD', title: 'x', target_value: 1 })
  })

  it('shows who each requirement applies to and lets me remove only mine', async () => {
    render(wrap(<RequirementsPage />))
    expect(await screen.findByText('Platform-wide')).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'All my PhD students' })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Remove' })).toHaveLength(1)
  })

  it('adds a requirement for one of my students', async () => {
    render(wrap(<RequirementsPage />))
    await screen.findByRole('option', { name: 'Only melisa' })
    fireEvent.change(screen.getByLabelText('Applies to'), { target: { value: 's1' } })
    fireEvent.change(screen.getByPlaceholderText('Requirement title *'), { target: { value: 'Present at the retreat' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add requirement' }))
    await waitFor(() => expect(supervisionApi.createRequirement).toHaveBeenCalledWith(expect.objectContaining({ title: 'Present at the retreat', student_id: 's1' })))
  })
})
