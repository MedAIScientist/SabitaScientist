// EvoScientist/pm/frontend/src/components/__tests__/AiRunsTab.test.tsx
import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AiRunsTab } from '../AiRunsTab'
import type { Task } from '../../api'

vi.mock('../../api', () => ({
  api: {
    listRuns: vi.fn().mockResolvedValue([]),
    createRun: vi.fn().mockResolvedValue({ id: 'r1', status: 'pending', agent_type: 'research', prompt: 'p', task_id: 't1', project_id: 'p1', output: null, error: null, started_at: null, finished_at: null, created_by: 'u1', created_at: '2026-01-01' }),
    cancelRun: vi.fn().mockResolvedValue(undefined),
    addComment: vi.fn().mockResolvedValue({}),
  },
}))

vi.mock('../../hooks/useRunStream', () => ({
  useRunStream: vi.fn(() => ({ output: '', isStreaming: false, streamStatus: 'idle' })),
}))

const MOCK_TASK: Task = {
  id: 't1', project_id: 'p1', title: 'Gel electrophoresis',
  description: 'Run gel for CRISPR verification',
  assignee_id: null, status: 'todo', priority: 'medium',
  deadline: null, session_id: null, created_by: 'u1',
  created_at: '2026-01-01', updated_at: '2026-01-01',
}

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
}

describe('AiRunsTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders all 4 agent buttons', () => {
    render(wrap(<AiRunsTab task={MOCK_TASK} projectId="p1" />))
    expect(screen.getByText(/Research/i)).toBeInTheDocument()
    expect(screen.getByText(/Code/i)).toBeInTheDocument()
    expect(screen.getByText(/Analysis/i)).toBeInTheDocument()
    expect(screen.getByText(/Writing/i)).toBeInTheDocument()
  })

  it('pre-fills prompt from task title and description', () => {
    render(wrap(<AiRunsTab task={MOCK_TASK} projectId="p1" />))
    const textarea = screen.getByRole('textbox')
    expect((textarea as HTMLTextAreaElement).value).toContain('Gel electrophoresis')
  })

  it('RUN button is enabled when Research is selected and prompt is non-empty', () => {
    render(wrap(<AiRunsTab task={MOCK_TASK} projectId="p1" />))
    const btn = screen.getByRole('button', { name: /RUN SABITA AI/i })
    expect(btn).not.toBeDisabled()
  })

  it('shows NO PREVIOUS RUNS when run list is empty', async () => {
    render(wrap(<AiRunsTab task={MOCK_TASK} projectId="p1" />))
    await waitFor(() =>
      expect(screen.getByText(/NO PREVIOUS RUNS/i)).toBeInTheDocument()
    )
  })

  it('shows run history when runs exist', async () => {
    const { api } = await import('../../api')
    vi.mocked(api.listRuns).mockResolvedValue([{
      id: 'r1', task_id: 't1', project_id: 'p1',
      agent_type: 'research', prompt: 'p', status: 'done',
      output: 'Protocol found.', error: null,
      started_at: '2026-01-01T00:00:00Z', finished_at: '2026-01-01T00:01:00Z',
      created_by: 'u1', created_at: '2026-01-01T00:00:00Z',
    }])
    render(wrap(<AiRunsTab task={MOCK_TASK} projectId="p1" />))
    await waitFor(() => expect(screen.getByText(/RESEARCH/i)).toBeInTheDocument())
  })
})
