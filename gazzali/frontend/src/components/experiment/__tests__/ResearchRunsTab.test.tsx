import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ResearchRunsTab } from '../ResearchRunsTab'
import { api, type ResearchRun } from '../../../api'

const WAITING: ResearchRun = {
  id: 'run1', experiment_id: 'e1', project_id: 'p1', lab_id: 'l1',
  topic: 'Does class weighting raise minority recall?', mode: 'co-pilot', dataset: null, irb_id: null,
  status: 'waiting', stage: 9, stage_name: 'EXPERIMENT_DESIGN',
  waiting: { stage: 9, stage_name: 'EXPERIMENT_DESIGN', reason: 'gate', since: '2026-10-03T00:00:00Z', context_summary: '240-cell factorial', output_files: ['stage-09/exp_plan.yaml'] },
  error: null, created_at: '2026-10-03T00:00:00Z', updated_at: '2026-10-03T00:00:00Z',
}

vi.mock('../../../api', () => ({
  api: {
    listResearchRuns: vi.fn(),
    startResearchRun: vi.fn(),
    respondResearchGate: vi.fn(),
    cancelResearchRun: vi.fn(),
    researchRunFile: vi.fn(),
    listIrbs: vi.fn().mockResolvedValue([]),
  },
}))

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
}

describe('ResearchRunsTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.listResearchRuns).mockResolvedValue([WAITING])
    vi.mocked(api.respondResearchGate).mockResolvedValue({ ...WAITING, status: 'running', waiting: null })
    vi.mocked(api.startResearchRun).mockResolvedValue({ ...WAITING, id: 'run2', status: 'running', waiting: null })
  })

  it('starts a CoPilot run with the hypothesis as the question', async () => {
    render(wrap(<ResearchRunsTab projectId="p1" experimentId="e1" hypothesis="Class weighting raises minority recall" />))
    fireEvent.click(screen.getByRole('button', { name: 'Run with AutoResearchClaw' }))
    await waitFor(() => expect(api.startResearchRun).toHaveBeenCalledWith('p1', 'e1', {
      topic: 'Class weighting raises minority recall', mode: 'co-pilot',
    }))
  })

  it('a dataset needs an IRB before the run can start', async () => {
    render(wrap(<ResearchRunsTab projectId="p1" experimentId="e1" hypothesis="Class weighting raises minority recall" />))
    fireEvent.change(screen.getByPlaceholderText(/retina/), { target: { value: 'retina/fundus' } })
    expect(screen.getByRole('button', { name: 'Run with AutoResearchClaw' })).toBeDisabled()
  })

  it('shows a waiting gate and sends the guidance with the decision', async () => {
    render(wrap(<ResearchRunsTab projectId="p1" experimentId="e1" />))
    expect(await screen.findByText('240-cell factorial')).toBeInTheDocument()
    expect(screen.getByText(/project team decides/)).toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText(/60 cells/), { target: { value: 'use 60 cells' } })
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
    await waitFor(() => expect(api.respondResearchGate).toHaveBeenCalledWith('run1', {
      action: 'approve', guidance: 'use 60 cells', message: 'use 60 cells',
    }))
  })
})
