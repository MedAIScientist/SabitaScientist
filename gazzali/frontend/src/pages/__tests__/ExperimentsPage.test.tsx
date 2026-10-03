import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ExperimentsPage } from '../ExperimentsPage'
import type { Experiment } from '../../api'

vi.mock('../../api', () => ({
  api: {
    getProject: vi.fn().mockResolvedValue({
      id: 'p1', name: 'CRISPR', members: [{ user_id: 'u1', username: 'owner', role: 'owner', added_at: '' }],
      description: null, created_by: 'u1', created_at: '', archived_at: null,
    }),
    listExperiments: vi.fn().mockResolvedValue([]),
    createExperiment: vi.fn().mockResolvedValue({
      id: 'exp1', project_id: 'p1', name: 'Western Blot', hypothesis: null,
      protocol: null, status: 'planned', tags: [], deadline: null,
      created_by: 'u1', created_at: '2026-01-01', updated_at: '2026-01-01',
    }),
    createTask: vi.fn().mockResolvedValue({}),
  },
  listPhases: vi.fn().mockResolvedValue([]),
}))

vi.mock('../../auth', () => ({
  useAuth: vi.fn(() => ({ username: 'owner', token: 'tok' })),
}))

vi.mock('../../components/ExperimentDetail', () => ({
  ExperimentDetail: () => <div data-testid="experiment-detail" />,
}))

const MOCK_EXP: Experiment = {
  id: 'exp1', project_id: 'p1', name: 'Western Blot #1',
  hypothesis: 'Protein expressed', protocol: null, status: 'planned',
  tags: ['blot'], deadline: null, created_by: 'u1',
  created_at: '2026-01-01', updated_at: '2026-01-01',
}

const PHASE = {
  id: 'ph1', project_id: 'p1', name: 'Data Analysis', color: '#8b5cf6',
  position: 0, target_date: null, created_by: 'u1', created_at: '2026-01-01',
}

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/projects/p1/experiments']}>
        <Routes>
          <Route path="/projects/:id/experiments" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ExperimentsPage', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    const { api, listPhases } = await import('../../api')
    vi.mocked(api.listExperiments).mockResolvedValue([])
    vi.mocked(listPhases).mockResolvedValue([])
  })

  it('renders project name in header', async () => {
    render(wrap(<ExperimentsPage />))
    await waitFor(() => expect(screen.getByText(/CRISPR/i)).toBeInTheDocument())
  })

  it('shows empty state when no experiments', async () => {
    render(wrap(<ExperimentsPage />))
    await waitFor(() => expect(screen.getByText(/NO EXPERIMENTS/i)).toBeInTheDocument())
  })

  it('shows experiment cards when experiments exist', async () => {
    const { api } = await import('../../api')
    vi.mocked(api.listExperiments).mockResolvedValue([MOCK_EXP])
    render(wrap(<ExperimentsPage />))
    await waitFor(() => expect(screen.getByText('Western Blot #1')).toBeInTheDocument())
  })

  it('names the create action instead of hiding it behind a + NEW menu', async () => {
    render(wrap(<ExperimentsPage />))
    const newBtn = await waitFor(() => screen.getByRole('button', { name: /EXPERIMENT/i }))
    expect(newBtn).toBeInTheDocument()
  })

  it('creates an experiment with the phase picked in the dialog', async () => {
    const { api, listPhases } = await import('../../api')
    vi.mocked(listPhases).mockResolvedValue([PHASE])
    render(wrap(<ExperimentsPage />))

    fireEvent.click(await screen.findByRole('button', { name: /EXPERIMENT/i }))

    const nameInput = await screen.findByPlaceholderText(/Denoise cohort/i)
    fireEvent.change(nameInput, { target: { value: 'Denoise cohort' } })
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'ph1' } })
    fireEvent.click(screen.getByRole('button', { name: /^CREATE$/i }))

    await waitFor(() => expect(api.createExperiment).toHaveBeenCalledWith('p1', {
      name: 'Denoise cohort', phase_id: 'ph1', hypothesis: null,
    }))
  })

  it('will not create an experiment without a name', async () => {
    const { api } = await import('../../api')
    render(wrap(<ExperimentsPage />))

    fireEvent.click(await screen.findByRole('button', { name: /EXPERIMENT/i }))
    await screen.findByPlaceholderText(/Denoise cohort/i)
    fireEvent.click(screen.getByRole('button', { name: /^CREATE$/i }))

    expect(api.createExperiment).not.toHaveBeenCalled()
  })
})
