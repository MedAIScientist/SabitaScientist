import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ExperimentDetail } from '../ExperimentDetail'
import type { Experiment } from '../../api'

vi.mock('../../api', () => ({
  api: {
    getExperiment: vi.fn().mockResolvedValue(null),
    updateExperiment: vi.fn().mockResolvedValue({}),
    deleteExperiment: vi.fn().mockResolvedValue(undefined),
    listLinkedTasks: vi.fn().mockResolvedValue([]),
    listTasks: vi.fn().mockResolvedValue([]),
    linkTask: vi.fn().mockResolvedValue({}),
    unlinkTask: vi.fn().mockResolvedValue(undefined),
    listEntries: vi.fn().mockResolvedValue([]),
    createEntry: vi.fn().mockResolvedValue({ id: 'e1', type: 'note', title: 'T', body: '', experiment_id: 'exp1', author_id: null, created_at: '', updated_at: '' }),
    updateEntry: vi.fn().mockResolvedValue({}),
    deleteEntry: vi.fn().mockResolvedValue(undefined),
  },
}))

vi.mock('../EntryEditor', () => ({
  EntryEditor: ({ onCancel }: { onCancel: () => void }) => (
    <div data-testid="entry-editor"><button onClick={onCancel}>CANCEL</button></div>
  ),
}))

const MOCK_EXP: Experiment = {
  id: 'exp1', project_id: 'p1', name: 'Western Blot #1',
  hypothesis: 'Protein is expressed', protocol: null,
  status: 'planned', tags: ['blot', 'protein'], deadline: null,
  created_by: 'u1', created_at: '2026-01-01', updated_at: '2026-01-01',
}

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
}

describe('ExperimentDetail', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('renders experiment name and status', () => {
    render(wrap(<ExperimentDetail experiment={MOCK_EXP} projectId="p1" onClose={vi.fn()} />))
    expect(screen.getByText('Western Blot #1')).toBeInTheDocument()
    expect(screen.getByText('PLANNED')).toBeInTheDocument()
  })

  it('renders OVERVIEW, NOTES, RESULTS tabs', () => {
    render(wrap(<ExperimentDetail experiment={MOCK_EXP} projectId="p1" onClose={vi.fn()} />))
    expect(screen.getByRole('button', { name: /OVERVIEW/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /NOTES/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /RESULTS/i })).toBeInTheDocument()
  })

  it('shows hypothesis in OVERVIEW tab', () => {
    render(wrap(<ExperimentDetail experiment={MOCK_EXP} projectId="p1" onClose={vi.fn()} />))
    expect(screen.getByText('Protein is expressed')).toBeInTheDocument()
  })

  it('switches to NOTES tab and shows Add Note button', async () => {
    render(wrap(<ExperimentDetail experiment={MOCK_EXP} projectId="p1" onClose={vi.fn()} />))
    fireEvent.click(screen.getByRole('button', { name: /NOTES/i }))
    await waitFor(() => expect(screen.getByText(/ADD NOTE/i)).toBeInTheDocument())
  })

  it('switches to RESULTS tab and shows Add Result button', async () => {
    render(wrap(<ExperimentDetail experiment={MOCK_EXP} projectId="p1" onClose={vi.fn()} />))
    fireEvent.click(screen.getByRole('button', { name: /RESULTS/i }))
    await waitFor(() => expect(screen.getByText(/ADD RESULT/i)).toBeInTheDocument())
  })

  it('calls onClose when ✕ is clicked', () => {
    const onClose = vi.fn()
    render(wrap(<ExperimentDetail experiment={MOCK_EXP} projectId="p1" onClose={onClose} />))
    fireEvent.click(screen.getByRole('button', { name: /✕/ }))
    expect(onClose).toHaveBeenCalled()
  })
})
