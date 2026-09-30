import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ProjectDataPage } from '../ProjectDataPage'

vi.mock('../../api', () => ({
  api: {
    getProject: vi.fn(),
    listDatasets: vi.fn(),
    listProjectDeidRuns: vi.fn(),
    listProjectCvat: vi.fn(),
    listProjectWebknossos: vi.fn(),
    listProjectSandboxes: vi.fn(),
    listProjectAssetLinks: vi.fn(),
  },
}))

import { api } from '../../api'

const mocked = vi.mocked(api)

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/projects/p1/data']}>
        <Routes>
          <Route path="/projects/:id/data" element={<ProjectDataPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const grantedDataset = {
  id: 'd1', name: 'DX ankle cohort', modality: 'DX', status: 'approved', lab_id: 'l1', bucket: 'ds-d1',
  grants: [{ project_id: 'p1', admin_approved_at: '2026-08-01', revoked_at: null }],
}
const ungrantedDataset = {
  id: 'd2', name: 'Someone else cohort', modality: 'CT', status: 'approved', lab_id: 'l1',
  grants: [{ project_id: 'p9', admin_approved_at: '2026-08-01', revoked_at: null }],
}
const revokedDataset = {
  id: 'd3', name: 'Revoked cohort', modality: 'MR', status: 'approved', lab_id: 'l1', bucket: 'ds-d3',
  grants: [{ project_id: 'p1', admin_approved_at: '2026-08-01', revoked_at: '2026-09-01' }],
}

beforeEach(() => {
  vi.clearAllMocks()
  mocked.getProject.mockResolvedValue({ id: 'p1', name: 'Ankle study' } as any)
  mocked.listDatasets.mockResolvedValue([] as any)
  mocked.listProjectDeidRuns.mockResolvedValue([] as any)
  mocked.listProjectCvat.mockResolvedValue([] as any)
  mocked.listProjectWebknossos.mockResolvedValue([] as any)
  mocked.listProjectSandboxes.mockResolvedValue([] as any)
  mocked.listProjectAssetLinks.mockResolvedValue([] as any)
})

describe('ProjectDataPage', () => {
  it('lists each kind of asset with its status', async () => {
    mocked.listProjectDeidRuns.mockResolvedValue([
      { id: 'r12345678', pipeline_id: 'pl1', project_id: 'p1', status: 'completed',
        input_location: 's3://in', output_location: 's3://out',
        records_processed: 512, completed_at: '2026-09-01' },
    ] as any)
    mocked.listProjectCvat.mockResolvedValue([
      { id: 'c1', project_id: 'p1', cvat_id: 7, name: 'Ankle annotations',
        status: 'annotating', num_images: 120, num_annotations: 340 },
    ] as any)
    mocked.listProjectWebknossos.mockResolvedValue([
      { id: 'w1', project_id: 'p1', name: 'EM volume', directory_name: 'em-1',
        status: 'segmenting', num_skeletons: 3, num_volumes: 9 },
    ] as any)
    mocked.listProjectSandboxes.mockResolvedValue([
      { id: 's1', project_id: 'p1', name: 'analysis box', status: 'active',
        access_url: null, expires_at: '2026-12-01T00:00:00Z' },
    ] as any)

    renderPage()

    expect(await screen.findByText('Ankle annotations')).toBeInTheDocument()
    expect(screen.getByText('EM volume')).toBeInTheDocument()
    expect(screen.getByText('analysis box')).toBeInTheDocument()
    expect(screen.getByText(/Run r1234567/)).toBeInTheDocument()
    expect(screen.getByText(/512 records/)).toBeInTheDocument()
    expect(screen.getByText(/120 images · 340 annotations/)).toBeInTheDocument()
    expect(screen.getByText(/4 assets/)).toBeInTheDocument()
  })

  it('only shows datasets actually released to this project', async () => {
    mocked.listDatasets.mockResolvedValue([
      grantedDataset, ungrantedDataset, revokedDataset,
    ] as any)

    renderPage()

    // Listed twice: as an asset row and in the JupyterHub bucket table.
    expect((await screen.findAllByText('DX ankle cohort')).length).toBeGreaterThan(0)
    expect(screen.queryByText('Someone else cohort')).toBeNull()
    expect(screen.queryByText('Revoked cohort')).toBeNull()
  })

  it('shows the bucket of each granted dataset for use in JupyterHub, and only those', async () => {
    mocked.listDatasets.mockResolvedValue([grantedDataset, revokedDataset] as any)

    renderPage()

    expect(await screen.findByText('Using this data in JupyterHub')).toBeInTheDocument()
    expect(screen.getByText('ds-d1')).toBeInTheDocument()
    expect(screen.queryByText('ds-d3')).toBeNull()  // revoked grant: no access, no bucket shown
    expect(screen.getAllByText(/approved, waiting for delivery/).length).toBeGreaterThan(0)
  })

  it('names the experiments using each asset (reverse lineage)', async () => {
    mocked.listProjectCvat.mockResolvedValue([
      { id: 'c1', project_id: 'p1', cvat_id: 7, name: 'Ankle annotations',
        status: 'annotating', num_images: 120, num_annotations: 340 },
    ] as any)
    mocked.listProjectAssetLinks.mockResolvedValue([
      { experiment_id: 'e1', experiment_name: 'Denoise cohort', asset_type: 'cvat_project',
        asset_id: 'c1', role: 'output' },
      { experiment_id: 'e2', experiment_name: 'Segment study', asset_type: 'cvat_project',
        asset_id: 'c1', role: 'input' },
    ] as any)

    renderPage()

    expect(await screen.findByText(/^USED BY$/i)).toBeInTheDocument()
    expect(screen.getByText(/Denoise cohort/)).toBeInTheDocument()
    expect(screen.getByText(/Segment study/)).toBeInTheDocument()
    expect(screen.getByText(/2 experiment links/)).toBeInTheDocument()
  })

  it('explains itself when the project has no data yet', async () => {
    renderPage()
    expect(await screen.findByText(/No data assets for this project yet/)).toBeInTheDocument()
    expect(screen.getAllByText('— none —').length).toBe(5)
  })

  it('offers an external link for CVAT annotation projects', async () => {
    mocked.listProjectCvat.mockResolvedValue([
      { id: 'c1', project_id: 'p1', cvat_id: 7, name: 'Ankle annotations',
        status: 'annotating', num_images: 1, num_annotations: 0 },
    ] as any)

    renderPage()

    const link = await screen.findByRole('link', { name: /OPEN/i })
    expect(link).toHaveAttribute('href', '/cvat/')
    expect(link).toHaveAttribute('target', '_blank')
  })
})
