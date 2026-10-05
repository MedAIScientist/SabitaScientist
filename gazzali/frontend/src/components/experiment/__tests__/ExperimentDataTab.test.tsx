import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi, beforeEach } from 'vitest'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ExperimentMetricsTab } from '../ExperimentMetricsTab'

vi.mock('@tanstack/react-query', () => ({
  useMutation: vi.fn(),
  useQuery: vi.fn(),
  useQueryClient: vi.fn(),
}))
vi.mock('../../../api', () => ({
  api: {
    listExperimentAssets: vi.fn(),
    linkExperimentAsset: vi.fn(),
    unlinkExperimentAsset: vi.fn(),
    listDatasets: vi.fn(() => Promise.resolve([])),
    listProjectDeidRuns: vi.fn(() => Promise.resolve([])),
    listProjectCvat: vi.fn(() => Promise.resolve([])),
    listProjectWebknossos: vi.fn(() => Promise.resolve([])),
    listProjectSandboxes: vi.fn(() => Promise.resolve([])),
    listExperimentMetrics: vi.fn(),
    createExperimentMetric: vi.fn(),
    deleteExperimentMetric: vi.fn(),
  },
  EXPERIMENT_ASSET_ROLES: ['input', 'processing', 'output', 'reference'],
  EXPERIMENT_ASSET_TYPE_LABELS: {
    dataset: 'IMAGING DATASET',
    pipeline_run: 'DE-ID RUN',
    cvat_project: 'CVAT ANNOTATION',
    webknossos_dataset: 'WEBKNOSSOS SEGMENTATION',
    sandbox: 'SANDBOX',
  },
}))

const mockedUseQuery = vi.mocked(useQuery)
const mockedUseMutation = vi.mocked(useMutation)
const mockedUseQueryClient = vi.mocked(useQueryClient)

/**
 * Answer by query key rather than by call order: the tab issues two queries whose
 * order is an implementation detail, so a call-ordered mock would be brittle.
 */
function respondWith(byKey: Record<string, unknown>) {
  mockedUseQuery.mockImplementation((options: any) => {
    const key = options?.queryKey?.[0]
    return { data: byKey[key] ?? [], isLoading: false } as any
  })
}

beforeEach(() => {
  mockedUseQueryClient.mockReturnValue({ invalidateQueries: vi.fn() } as any)
  mockedUseMutation.mockReturnValue({ mutate: vi.fn(), isPending: false } as any)
})

const datasetAsset = {
  experiment_id: 'e1', asset_type: 'dataset' as const, asset_id: 'd1',
  role: 'input' as const, note: null, linked_at: '2026-01-01', linked_by: 'u1',
  label: 'DX ayak/bilek 2019-2025', detail: 'DX · approved',
}
const cvatAsset = {
  experiment_id: 'e1', asset_type: 'cvat_project' as const, asset_id: 'c1',
  role: 'output' as const, note: null, linked_at: '2026-01-02', linked_by: 'u1',
  label: 'Ankle annotations', detail: 'annotating · 120 images',
}

const metric = {
  id: 'm1', experiment_id: 'e1', name: 'dice', value: 0.8734,
  unit: null, split: 'test', n: 42, stderr: 0.012,
  source_attachment_id: 'a1', recorded_by: 'u1', created_at: '2026-01-01',
}

describe('ExperimentMetricsTab', () => {
  test('shows recorded metrics with source attribution', () => {
    respondWith({ 'experiment-metrics': [metric] })
    render(<ExperimentMetricsTab projectId="p1" experimentId="e1" />)

    expect(screen.getByText('0.8734 ± 0.012')).toBeInTheDocument()
    expect(screen.getByText(/dice · test · n=42 · from table/)).toBeInTheDocument()
    expect(screen.getByText(/1 number · 1 from uploaded tables/i)).toBeInTheDocument()
  })

  test('formats a metric with a unit', () => {
    respondWith({
      'experiment-metrics': [{ ...metric, name: 'volume', value: 1234.5, unit: 'mm3', stderr: null }],
    })
    render(<ExperimentMetricsTab projectId="p1" experimentId="e1" />)
    expect(screen.getByText('1,234.5 mm3')).toBeInTheDocument()
  })

  test('will not submit without a name and a numeric value', () => {
    respondWith({})
    render(<ExperimentMetricsTab projectId="p1" experimentId="e1" />)

    const button = screen.getByRole('button', { name: /Add this number/i })
    expect(button).toBeDisabled()

    fireEvent.change(screen.getByLabelText('What did you measure'), { target: { value: 'dice' } })
    expect(button).toBeDisabled()  // still missing the value

    fireEvent.change(screen.getByLabelText('Value'), { target: { value: '0.9' } })
    expect(button).not.toBeDisabled()
  })

  test('records a metric and posts the parsed number', () => {
    const mutate = vi.fn()
    mockedUseMutation.mockReturnValue({ mutate, isPending: false } as any)
    respondWith({})
    render(<ExperimentMetricsTab projectId="p1" experimentId="e1" />)

    fireEvent.change(screen.getByLabelText('What did you measure'), { target: { value: 'iou' } })
    fireEvent.change(screen.getByLabelText('Value'), { target: { value: '0.81' } })
    fireEvent.click(screen.getByRole('button', { name: /Add this number/i }))

    expect(mutate).toHaveBeenCalled()
  })

  test('explains the empty state', () => {
    respondWith({})
    render(<ExperimentMetricsTab projectId="p1" experimentId="e1" />)
    expect(screen.getByText(/No numbers yet/)).toBeInTheDocument()
  })
})
