import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ExperimentDataTab } from '../ExperimentDataTab'
import { ExperimentMetricsTab } from '../ExperimentMetricsTab'
import { api } from '../../../api'

vi.mock('../../../api', () => ({
  api: {
    listExperimentAssets: vi.fn(), linkExperimentAsset: vi.fn(), unlinkExperimentAsset: vi.fn(),
    listDatasets: vi.fn(), listProjectDeidRuns: vi.fn(), listProjectCvat: vi.fn(), listProjectWebknossos: vi.fn(),
    listExperimentMetrics: vi.fn(), cvatProgress: vi.fn(), importCvatMetrics: vi.fn(),
    importMetricsCsv: vi.fn(), createExperimentMetric: vi.fn(), deleteExperimentMetric: vi.fn(),
  },
}))

const wrap = (ui: React.ReactNode) => render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>)
const cvatLink = { experiment_id: 'e', asset_type: 'cvat_project', asset_id: 'c1', role: 'processing', note: null, linked_at: '', linked_by: 'u', label: 'Ankle labels', detail: 'annotating' }

beforeEach(() => {
  vi.mocked(api.listDatasets).mockResolvedValue([{ id: 'd1', name: 'Ankle DX cohort', status: 'sealed' }, { id: 'd2', name: 'Draft cohort', status: 'draft' }] as never)
  vi.mocked(api.listProjectDeidRuns).mockResolvedValue([])
  vi.mocked(api.listProjectCvat).mockResolvedValue([{ id: 'c1', name: 'Ankle labels', status: 'annotating', cvat_id: 29 }] as never)
  vi.mocked(api.listProjectWebknossos).mockResolvedValue([])
  vi.mocked(api.listExperimentMetrics).mockResolvedValue([])
  vi.mocked(api.linkExperimentAsset).mockResolvedValue({} as never)
})

describe('ExperimentDataTab flow', () => {
  it('asks nothing when no data is linked, then offers usable cohorts as input without a role picker', async () => {
    vi.mocked(api.listExperimentAssets).mockResolvedValue([])
    wrap(<ExperimentDataTab projectId="p" experimentId="e" />)
    expect(await screen.findByText('No data linked')).toBeInTheDocument()
    expect(screen.queryByText('Annotation')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Link a cohort or annotation' }))
    expect(await screen.findByText('Ankle DX cohort')).toBeInTheDocument()
    expect(screen.queryByText('Draft cohort')).not.toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: 'Use' })[0])
    await waitFor(() => expect(api.linkExperimentAsset).toHaveBeenCalledWith('p', 'e', { asset_type: 'dataset', asset_id: 'd1', role: 'input' }))
  })

  it('shows live CVAT progress, links to CVAT, and sends counts to Results', async () => {
    vi.mocked(api.listExperimentAssets).mockResolvedValue([cvatLink] as never)
    vi.mocked(api.cvatProgress).mockResolvedValue({ tasks: 1, jobs: 2, jobs_done: 1, frames_total: 20, frames_done: 10,
      by_assignee: [{ name: 'ayse', jobs: 1, jobs_done: 1, frames: 10, frames_done: 10 }, { name: 'mert', jobs: 1, jobs_done: 0, frames: 10, frames_done: 0 }] })
    vi.mocked(api.importCvatMetrics).mockResolvedValue({ saved: 4, summary: { labels: { fracture: 3 }, frames_annotated: 4, frames_total: 20 } })
    wrap(<ExperimentDataTab projectId="p" experimentId="e" />)
    expect(await screen.findByText('10 of 20 images finished')).toBeInTheDocument()
    expect(screen.getByText('ayse: 10/10 · mert: 0/10')).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: /Open in CVAT/ })).toHaveAttribute('href', '/cvat/projects/29')
    fireEvent.click(screen.getByRole('button', { name: 'Send counts to Results' }))
    expect(await screen.findByText(/4 numbers sent to Results: 4 images annotated, 3 fracture/)).toBeInTheDocument()
  })
})

describe('ExperimentMetricsTab CSV import', () => {
  it('previews a results table and saves only after confirmation', async () => {
    vi.mocked(api.importMetricsCsv).mockImplementation(async (_p, _e, _t, save) =>
      ({ metrics: [{ name: 'AUC', value: 0.91, unit: null, split: 'test', n: null, stderr: null }], saved: save ? 1 : 0 }))
    wrap(<ExperimentMetricsTab projectId="p" experimentId="e" />)
    const file = new File(['metric,value\nAUC,0.91\n'], 'r.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByLabelText('Results table file'), { target: { files: [file] } })
    expect(await screen.findByText(/Found 1 number/)).toBeInTheDocument()
    expect(api.importMetricsCsv).toHaveBeenLastCalledWith('p', 'e', 'metric,value\nAUC,0.91\n', false)
    fireEvent.click(screen.getByRole('button', { name: 'Save 1 numbers' }))
    await waitFor(() => expect(api.importMetricsCsv).toHaveBeenLastCalledWith('p', 'e', 'metric,value\nAUC,0.91\n', true))
  })
})
