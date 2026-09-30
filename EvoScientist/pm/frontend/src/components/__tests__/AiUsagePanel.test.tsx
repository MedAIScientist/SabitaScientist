import { render, screen } from '@testing-library/react'
import { describe, test, expect, vi, beforeEach } from 'vitest'
import { useQuery } from '@tanstack/react-query'
import { AiUsagePanel } from '../AiUsagePanel'

vi.mock('@tanstack/react-query', () => ({ useQuery: vi.fn() }))
vi.mock('../../api', () => ({ aiUsageApi: { summary: vi.fn() } }))

const EMPTY = {
  window_days: 30,
  calls: 0,
  tokens: { provider_reported: 0, estimated: 0, prompt: 0, completion: 0 },
  avg_duration_ms: null,
  by_task: [],
  by_model: [],
}

function mockQuery(data: unknown) {
  vi.mocked(useQuery).mockReturnValue({ data, isLoading: false, error: null } as never)
}

describe('AiUsagePanel', () => {
  beforeEach(() => vi.clearAllMocks())

  test('says so when nothing was recorded', () => {
    mockQuery(EMPTY)
    render(<AiUsagePanel />)
    expect(screen.getByText(/No AI calls recorded/i)).toBeInTheDocument()
  })

  test('reports provider-measured tokens', () => {
    mockQuery({
      ...EMPTY,
      calls: 3,
      tokens: { provider_reported: 4200, estimated: 0, prompt: 3000, completion: 1200 },
      by_task: [{ label: 'draft-section', calls: 3, provider_tokens: 4200, estimated_tokens: 0 }],
      by_model: [{ label: 'llama-3.3-70b', calls: 3, provider_tokens: 4200, estimated_tokens: 0 }],
    })
    render(<AiUsagePanel />)
    // The measured total shows in the headline stat and again in the breakdown.
    expect(screen.getAllByText('4,200').length).toBeGreaterThan(0)
    // Appears both in the breakdown and in the "heaviest task" line.
    expect(screen.getAllByText('draft-section').length).toBeGreaterThan(0)
    expect(screen.queryByText(/ESTIMATED/i)).not.toBeInTheDocument()
  })

  test('never presents an estimate as a measurement', () => {
    mockQuery({
      ...EMPTY,
      calls: 2,
      tokens: { provider_reported: 1000, estimated: 250, prompt: 800, completion: 450 },
      by_task: [{ label: 'revise', calls: 2, provider_tokens: 1000, estimated_tokens: 250 }],
      by_model: [],
    })
    render(<AiUsagePanel />)

    // The measured total and the estimate stay visibly separate…
    expect(screen.getByText('1,000')).toBeInTheDocument()
    expect(screen.getByText('≈ 250')).toBeInTheDocument()
    // …and the panel explains which is which rather than silently adding them.
    expect(screen.getByText(/never added together/i)).toBeInTheDocument()
  })

  test('surfaces the heaviest task so the report is actionable', () => {
    mockQuery({
      ...EMPTY,
      calls: 5,
      tokens: { provider_reported: 900, estimated: 0, prompt: 500, completion: 400 },
      by_task: [
        { label: 'respond-to-reviewers', calls: 4, provider_tokens: 800, estimated_tokens: 0 },
        { label: 'revise', calls: 1, provider_tokens: 100, estimated_tokens: 0 },
      ],
      by_model: [],
    })
    render(<AiUsagePanel />)
    expect(screen.getByText(/Heaviest task/i).textContent).toContain('respond-to-reviewers')
  })

  test('reports a read failure instead of rendering zeros', () => {
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('403 Not permitted'),
    } as never)
    render(<AiUsagePanel />)
    expect(screen.getByText(/403 Not permitted/)).toBeInTheDocument()
  })
})
