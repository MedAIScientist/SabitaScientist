import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ApprovalsInbox } from '../ApprovalsInbox'

vi.mock('../../../api', () => ({ api: { imagingInbox: vi.fn(), proposeDatasetGrant: vi.fn(), adminApproveDataset: vi.fn() } }))
import { api } from '../../../api'
const mocked = vi.mocked(api)

const share = (over: Record<string, unknown> = {}) => ({
  action: 'propose-grant', dataset_id: 'd1', dataset_name: 'DX ayak bilek 2019', modality: 'DX',
  purpose: 'Fracture study', lab_name: 'test-lab', project_id: 'p1', project_name: 'test-project',
  requested_by: 'student1', accession_count: 12, retention_until: '2028-10-10', grant_id: null,
  irbs: [], blockers: [], renders: true, ...over,
})

function renderInbox() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}><ApprovalsInbox /></QueryClientProvider>)
}

beforeEach(() => {
  vi.resetAllMocks()
  mocked.proposeDatasetGrant.mockResolvedValue({} as never)
  mocked.adminApproveDataset.mockResolvedValue({} as never)
})

describe('ApprovalsInbox — sharing a dataset with a project', () => {
  it('a request with viewable images starts on JupyterHub and CVAT, and says what was asked', async () => {
    // 2026-10-17: a student who asked for viewable images was shown to their PI as JupyterHub-only.
    mocked.imagingInbox.mockResolvedValue([share({ requested_by: 'student3' })] as never)
    renderInbox()
    expect(await screen.findByText(/student3 asked for viewable images too/)).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /JupyterHub and CVAT/ })).toBeChecked()
    fireEvent.click(screen.getByRole('button', { name: 'Share with project' }))
    await waitFor(() => expect(mocked.proposeDatasetGrant).toHaveBeenCalledWith('d1', 'p1', { annotate: true }))
  })

  it('a request for the DICOM only starts on JupyterHub and asks for no annotation', async () => {
    mocked.imagingInbox.mockResolvedValue([share({ renders: false, requested_by: 'student2' })] as never)
    renderInbox()
    expect(await screen.findByText(/student2 asked for the DICOM files only/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Share with project' }))
    await waitFor(() => expect(mocked.proposeDatasetGrant).toHaveBeenCalledWith('d1', 'p1', {}))
  })

  it('the PI can still choose JupyterHub only for a request that had images', async () => {
    mocked.imagingInbox.mockResolvedValue([share()] as never)
    renderInbox()
    fireEvent.click(await screen.findByRole('radio', { name: /^JupyterHub \(read the DICOM files\)/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Share with project' }))
    await waitFor(() => expect(mocked.proposeDatasetGrant).toHaveBeenCalledWith('d1', 'p1', {}))
  })

  it('choosing JupyterHub and CVAT asks for annotation staging, with the task size', async () => {
    mocked.imagingInbox.mockResolvedValue([share()] as never)
    renderInbox()
    fireEvent.click(await screen.findByRole('radio', { name: /JupyterHub and CVAT/ }))
    fireEvent.change(screen.getByLabelText('Images per task'), { target: { value: '50' } })
    fireEvent.click(screen.getByRole('button', { name: 'Share with project' }))
    await waitFor(() => expect(mocked.proposeDatasetGrant).toHaveBeenCalledWith('d1', 'p1', { annotate: true, task_size: 50 }))
  })

  it('a dataset without viewable images cannot be sent to CVAT, and says why', async () => {
    mocked.imagingInbox.mockResolvedValue([share({ renders: false })] as never)
    renderInbox()
    expect(await screen.findByRole('radio', { name: /JupyterHub and CVAT/ })).toBeDisabled()
    expect(screen.getByText(/approved without viewable images/)).toBeInTheDocument()
  })
})

describe('ApprovalsInbox — the dataset id', () => {
  it('every card shows the dataset id, so the admin can find the cohort in Curator', async () => {
    mocked.imagingInbox.mockResolvedValue([share({ dataset_id: 'abcdef0123456789abcdef0123456789' })] as never)
    renderInbox()
    expect(await screen.findByTitle('Dataset id')).toHaveTextContent('abcdef0123456789abcdef0123456789')
  })
})

describe('ApprovalsInbox — reserving storage at the final approval', () => {
  const approve = (over: Record<string, unknown> = {}) => share({ action: 'admin-approve', retention_until: '2028-10-10', estimated_bytes: null, ...over })

  it('the reserved GiB travel with the approval as bytes', async () => {
    mocked.imagingInbox.mockResolvedValue([approve()] as never)
    renderInbox()
    fireEvent.change(await screen.findByLabelText('Storage to reserve (GiB)'), { target: { value: '5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Approve & release' }))
    await waitFor(() => expect(mocked.adminApproveDataset).toHaveBeenCalledWith('d1', '2028-10-10', 5 * 1024 ** 3))
  })

  it('left empty, it says the bucket would have no limit — and still lets the admin approve', async () => {
    mocked.imagingInbox.mockResolvedValue([approve()] as never)
    renderInbox()
    expect(await screen.findByText(/no size limit/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Approve & release' }))
    await waitFor(() => expect(mocked.adminApproveDataset).toHaveBeenCalledWith('d1', '2028-10-10', undefined))
  })

  it('starts from what the request already reserved, and refuses text that is not an amount', async () => {
    mocked.imagingInbox.mockResolvedValue([approve({ estimated_bytes: 3 * 1024 ** 3 })] as never)
    renderInbox()
    const field = await screen.findByLabelText('Storage to reserve (GiB)')
    expect(field).toHaveValue('3')
    fireEvent.change(field, { target: { value: 'lots' } })
    expect(screen.getByRole('button', { name: 'Approve & release' })).toBeDisabled()
  })
})
