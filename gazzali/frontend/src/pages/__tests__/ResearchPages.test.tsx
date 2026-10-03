import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ResearchMemoryPage } from '../ResearchMemoryPage'
import { ResearchEvaluationPage } from '../ResearchEvaluationPage'
import { api } from '../../api'

vi.mock('../../api', () => ({
  api: {
    listResearchLessons: vi.fn(), pinResearchLesson: vi.fn(), deleteResearchLesson: vi.fn(), researchEvaluation: vi.fn(),
  },
}))

function wrap(ui: React.ReactNode, path = '/') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <MemoryRouter initialEntries={[path]}>
      <QueryClientProvider client={qc}>
        <Routes><Route path="/labs/:id/research-memory" element={ui} /><Route path="/" element={ui} /></Routes>
      </QueryClientProvider>
    </MemoryRouter>
  )
}

describe('research pages', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.listResearchLessons).mockResolvedValue([
      { id: 'l1', run_id: 'r1', category: 'design', severity: 0.6, pinned: false, weight: 0.42, created_at: '2026-10-01T00:00:00Z',
        lesson: { description: '240-cell factorial exceeded the time budget', stage_name: 'experiment_design' } },
    ])
    vi.mocked(api.pinResearchLesson).mockResolvedValue({ id: 'l1', pinned: true })
    vi.mocked(api.researchEvaluation).mockResolvedValue({
      summary: { runs: 5, finished: 4, completion_rate: 0.8, mean_interventions: 1.4, mean_pi_quality: 7.5 },
      runs: [{ id: 'r1', topic: 'Class weighting', status: 'done', mode: 'co-pilot', created_at: '2026-10-01T00:00:00Z', stage: 23,
        interventions: 2, refines: 1, pivots: 0, retries: 1, unverified_in_paper: 0, pi_quality: 8, primary_metric: 0.91 }],
      gates: [{ stage: 9, stage_name: 'EXPERIMENT_DESIGN', approved: 5, redirected: 0, total: 5, approve_rate: 1, advice: 'Almost always approved: for routine runs, Gate-only mode would save this step.' }],
    })
  })

  it('lists lab lessons and pins one', async () => {
    render(wrap(<ResearchMemoryPage />, '/labs/lab1/research-memory'))
    expect(await screen.findByText('240-cell factorial exceeded the time budget')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Pin' }))
    await waitFor(() => expect(api.pinResearchLesson).toHaveBeenCalledWith('lab1', 'l1', true))
  })

  it('shows evaluation summary and gate advice in plain language', async () => {
    render(wrap(<ResearchEvaluationPage />))
    expect(await screen.findByText('80%')).toBeInTheDocument()
    expect(screen.getByText('9. Designing the experiment')).toBeInTheDocument()
    expect(screen.getByText(/Gate-only mode would save this step/)).toBeInTheDocument()
  })
})
