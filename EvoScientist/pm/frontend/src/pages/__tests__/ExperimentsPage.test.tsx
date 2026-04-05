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
  },
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
  beforeEach(() => { vi.clearAllMocks() })

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

  it('shows NEW EXPERIMENT button', async () => {
    render(wrap(<ExperimentsPage />))
    // The "+ NEW" dropdown trigger button should always be present
    const newBtn = await waitFor(() => screen.getByRole('button', { name: /\+ NEW/i }))
    expect(newBtn).toBeInTheDocument()
    // Opening the dropdown reveals the EXPERIMENT item
    fireEvent.click(newBtn)
    await waitFor(() => expect(screen.getByRole('button', { name: /EXPERIMENT/i })).toBeInTheDocument())
  })
})
