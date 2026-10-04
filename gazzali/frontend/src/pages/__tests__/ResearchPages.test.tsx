import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ResearchMemoryPage } from '../ResearchMemoryPage'
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
      quality_trend: [
        { id: 'r1', created_at: '2026-10-01T00:00:00Z', status: 'done', pi_quality: 8, interventions: 2, refines: 1, pivots: 0, retries: 1 },
      ],
      gate_economics: {
        top_intervention_stages: [],
        auto_approve_candidates: [
          { stage: 9, stage_name: 'EXPERIMENT_DESIGN', approve_rate: 1, total: 5 },
        ],
        min_decisions_for_advice: 5,
      },
      integrity: {
        papers_tracked: 1,
        papers_with_unverified_data: 0,
        unverified_total: 0,
        papers: [
          { publication_id: 'p1', title: 'Class weighting paper', pub_status: 'draft', unverified_in_results: 0, integrity_passed: true, integrity_at: '2026-10-01T00:00:00Z' },
        ],
      },
      outcomes: {
        runs_with_publication: 1,
        runs_with_metric: 1,
        finished_with_paper: 1,
        mean_primary_metric: 0.91,
        papers: [
          { publication_id: 'p1', title: 'Class weighting paper', pub_status: 'draft', unverified_in_results: 0, integrity_passed: true, integrity_at: '2026-10-01T00:00:00Z' },
        ],
      },
    })
  })

  it('lists lab lessons and pins one', async () => {
    render(wrap(<ResearchMemoryPage />, '/labs/lab1/research-memory'))
    expect(await screen.findByText('240-cell factorial exceeded the time budget')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Pin' }))
    await waitFor(() => expect(api.pinResearchLesson).toHaveBeenCalledWith('lab1', 'l1', true))
  })

})
