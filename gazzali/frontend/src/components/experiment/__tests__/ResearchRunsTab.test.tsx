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
    researchRunStages: vi.fn(),
    researchUsage: vi.fn(),
    researchDomains: vi.fn(),
    researchTopicCheck: vi.fn(),
    researchDatasets: vi.fn(),
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
    vi.mocked(api.startResearchRun).mockResolvedValue({ ...WAITING, id: 'run2', status: 'queued', waiting: null, queue_position: 1 })
    vi.mocked(api.researchRunFile).mockResolvedValue({ path: 'stage-09/exp_plan.yaml', content: 'conditions: 240' })
    vi.mocked(api.researchRunStages).mockResolvedValue({
      stages: [
        { stage: 8, status: 'done', duration_sec: 119, decision: 'proceed', error: null, artifacts: ['stage-08/hypotheses.md'], attempts: 1 },
        { stage: 9, status: 'done', duration_sec: 69, decision: 'refine', error: null, artifacts: ['stage-09/exp_plan.yaml'], attempts: 2 },
      ],
      topic_evaluation: { novelty: 2, specificity: 7, feasibility: 9, overall: 6, suggestion: '' },
    })
    vi.mocked(api.researchUsage).mockResolvedValue({ requests_last_minute: 4, limit_per_minute: 40, runs_running: 1, runs_waiting: 0, runs_queued: 0, max_concurrent: 1 })
    vi.mocked(api.researchDomains).mockResolvedValue([{ id: 'ml', label: 'Machine learning (tabular data)', guidance: 'Use 5 seeds.' }])
    vi.mocked(api.researchTopicCheck).mockResolvedValue({ novelty: 2, specificity: 7, feasibility: 9, overall: 6, suggestion: 'Use three datasets' })
    vi.mocked(api.researchDatasets).mockResolvedValue([{ id: 'd1', name: 'Fundus 2026', modality: 'CF', irb_ids: ['irb1'] }])
  })

  it('walks question → data → review and starts the run with the chosen dataset', async () => {
    render(wrap(<ResearchRunsTab projectId="p1" experimentId="e1" hypothesis="Class weighting raises minority recall" />))
    fireEvent.click(screen.getByRole('button', { name: 'Check my question' }))
    expect(await screen.findByText(/Suggestion: Use three datasets/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Kind of study'), { target: { value: 'ml' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next: data' }))
    const select = await screen.findByLabelText('Dataset')
    await screen.findByRole('option', { name: /Fundus 2026/ })
    fireEvent.change(select, { target: { value: 'd1' } })  // single IRB is filled in automatically
    fireEvent.click(screen.getByRole('button', { name: 'Next: review' }))
    expect(await screen.findByText(/a new run will wait in the queue/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Start the run' }))
    await waitFor(() => expect(api.startResearchRun).toHaveBeenCalledWith('p1', 'e1', {
      topic: 'Class weighting raises minority recall', mode: 'co-pilot', domain: 'ml', dataset_id: 'd1', irb_id: 'irb1',
    }))
  })

  it('shows the gate in plain language with a preview and quick replies', async () => {
    render(wrap(<ResearchRunsTab projectId="p1" experimentId="e1" />))
    expect(await screen.findAllByText(/Designing the experiment/)).not.toHaveLength(0)
    expect(screen.getByText(/the project team decides/)).toBeInTheDocument()
    expect(await screen.findAllByText('conditions: 240')).not.toHaveLength(0)
    fireEvent.click(screen.getByRole('button', { name: '+ Reduce the number of conditions' }))
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
    await waitFor(() => expect(api.respondResearchGate).toHaveBeenCalledWith('run1', {
      action: 'approve', guidance: 'Reduce the number of conditions', message: 'Reduce the number of conditions',
    }))
  })

  it('timeline marks a refined stage and opens its artifacts', async () => {
    render(wrap(<ResearchRunsTab projectId="p1" experimentId="e1" />))
    const stage9 = await screen.findByRole('listitem', { name: /Stage 9: Designing the experiment/ })
    await waitFor(() => expect(stage9.textContent).toContain('↻'))
    fireEvent.click(stage9)
    expect(await screen.findByText(/2 attempts/)).toBeInTheDocument()
    expect(screen.getByText('Topic score 6/10 · novelty 2 · specificity 7 · feasibility 9')).toBeInTheDocument()
  })
})
