import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ProjectFilesPage } from '../ProjectFilesPage'

const { listProjectAttachments, deleteAttachment, fetchAttachmentBlob } = vi.hoisted(() => ({
  listProjectAttachments: vi.fn(),
  deleteAttachment: vi.fn(),
  fetchAttachmentBlob: vi.fn(),
}))

vi.mock('../../api', () => ({
  api: {
    getProject: vi.fn().mockResolvedValue({ id: 'p1', name: 'Imaging study' }),
    listProjectAttachments,
    deleteAttachment,
    fetchAttachmentBlob,
  },
}))

const TASK_FILE = {
  id: 'a1', filename: 'cohort.csv', content_type: 'text/csv', size_bytes: 2048,
  classification: 'unclassified', created_at: '2026-10-01T09:00:00Z',
  uploaded_by: 'u1', uploader_name: 'kbkose',
  owner_kind: 'task' as const, owner_id: 't1', owner_title: 'Denoise the cohort',
  experiment_id: null,
}

const ENTRY_FILE = {
  id: 'a2', filename: 'figure.png', content_type: 'image/png', size_bytes: 4096,
  classification: 'unclassified', created_at: '2026-09-28T09:00:00Z',
  uploaded_by: 'u2', uploader_name: 'melisa',
  owner_kind: 'entry' as const, owner_id: 'e1', owner_title: 'Final run',
  experiment_id: 'x1',
}

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/projects/p1/files']}>
        <Routes>
          <Route path="/projects/:id/files" element={<ProjectFilesPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ProjectFilesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listProjectAttachments.mockResolvedValue([TASK_FILE, ENTRY_FILE])
    deleteAttachment.mockResolvedValue(undefined)
    fetchAttachmentBlob.mockResolvedValue(new Blob(['a,b\n'], { type: 'text/csv' }))
    URL.createObjectURL = vi.fn(() => 'blob:file')
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(window, 'open').mockReturnValue(null)
  })

  it('lists every file in the project with what it is attached to', async () => {
    wrap()

    expect(await screen.findByText('cohort.csv')).toBeInTheDocument()
    expect(screen.getByText('figure.png')).toBeInTheDocument()
    // Both owners are named, so a file can be found without knowing where it lives.
    expect(screen.getByText('Task · Denoise the cohort')).toBeInTheDocument()
    expect(screen.getByText('Experiment · Final run')).toBeInTheDocument()
    expect(screen.getByText(/2 files · 6\.0 KB/)).toBeInTheDocument()
  })

  it('filters to task or experiment files', async () => {
    wrap()
    await screen.findByText('cohort.csv')

    fireEvent.click(screen.getByRole('button', { name: 'Task files' }))
    await waitFor(() => expect(listProjectAttachments).toHaveBeenLastCalledWith('p1', 'task'))

    fireEvent.click(screen.getByRole('button', { name: 'Experiment files' }))
    await waitFor(() => expect(listProjectAttachments).toHaveBeenLastCalledWith('p1', 'entry'))

    fireEvent.click(screen.getByRole('button', { name: 'All files' }))
    await waitFor(() => expect(listProjectAttachments).toHaveBeenLastCalledWith('p1', undefined))
  })

  it('opens a file through the authenticated API', async () => {
    wrap()
    fireEvent.click(await screen.findByText('cohort.csv'))

    await waitFor(() => expect(fetchAttachmentBlob).toHaveBeenCalledWith('a1'))
    expect(window.open).toHaveBeenCalledWith('blob:file', '_blank', 'noopener')
  })

  it('reports a file that could not be opened', async () => {
    fetchAttachmentBlob.mockRejectedValue(new Error('Could not open the file'))
    wrap()
    fireEvent.click(await screen.findByText('cohort.csv'))

    expect(await screen.findByRole('status')).toHaveTextContent('Could not open the file')
  })

  it('deletes a file from the project view', async () => {
    wrap()
    await screen.findByText('cohort.csv')

    fireEvent.click(screen.getAllByTitle('Delete file')[0])

    await waitFor(() => expect(deleteAttachment).toHaveBeenCalledWith('a1'))
  })

  it('says so when the project has no files', async () => {
    listProjectAttachments.mockResolvedValue([])
    wrap()
    expect(await screen.findByText(/No files yet/)).toBeInTheDocument()
  })
})
