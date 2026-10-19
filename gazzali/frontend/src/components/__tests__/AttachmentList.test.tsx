import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AttachmentList } from '../AttachmentList'

const {
  listAttachments, uploadAttachment, listTaskAttachments, uploadTaskAttachment,
  deleteAttachment, fetchAttachmentBlob,
} = vi.hoisted(() => ({
  listAttachments: vi.fn(),
  uploadAttachment: vi.fn(),
  listTaskAttachments: vi.fn(),
  uploadTaskAttachment: vi.fn(),
  deleteAttachment: vi.fn(),
  fetchAttachmentBlob: vi.fn(),
}))

vi.mock('../../api', () => ({
  api: {
    listAttachments, uploadAttachment, listTaskAttachments, uploadTaskAttachment,
    deleteAttachment, fetchAttachmentBlob,
  },
}))

const FILE = {
  id: 'a1', entry_id: null, task_id: 't1', filename: 'cohort.csv',
  content_type: 'text/csv', size_bytes: 2048, uploaded_by: 'u1',
  created_at: '2026-01-01', download_url: 'http://garage/cohort.csv',
}

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

describe('AttachmentList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listTaskAttachments.mockResolvedValue([FILE])
    listAttachments.mockResolvedValue([])
    uploadTaskAttachment.mockResolvedValue(FILE)
    deleteAttachment.mockResolvedValue(undefined)
    fetchAttachmentBlob.mockResolvedValue(new Blob(['a,b\n'], { type: 'text/csv' }))
    // jsdom has neither of these; the component only needs them to exist.
    URL.createObjectURL = vi.fn(() => 'blob:preview')
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(window, 'open').mockReturnValue(null)
  })

  it('lists the files attached to a task', async () => {
    wrap(<AttachmentList target={{ kind: 'task', projectId: 'p1', taskId: 't1' }} accent="#ff8015" />)

    expect(await screen.findByText('cohort.csv')).toBeInTheDocument()
    expect(screen.getByText('2.0 KB')).toBeInTheDocument()
    expect(listTaskAttachments).toHaveBeenCalledWith('p1', 't1')
    expect(listAttachments).not.toHaveBeenCalled()
  })

  it('uploads to the task, not to an entry', async () => {
    wrap(<AttachmentList target={{ kind: 'task', projectId: 'p1', taskId: 't1' }} accent="#ff8015" />)
    await screen.findByText('cohort.csv')

    const file = new File(['a,b\n'], 'results.csv', { type: 'text/csv' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => expect(uploadTaskAttachment).toHaveBeenCalledWith('p1', 't1', file))
    expect(uploadAttachment).not.toHaveBeenCalled()
  })

  it('refuses a file type the server would reject anyway', async () => {
    wrap(<AttachmentList target={{ kind: 'task', projectId: 'p1', taskId: 't1' }} accent="#ff8015" />)
    await screen.findByText('cohort.csv')

    const exe = new File(['MZ'], 'app.exe', { type: 'application/x-msdownload' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [exe] } })

    expect(await screen.findByText(/not allowed/i)).toBeInTheDocument()
    expect(uploadTaskAttachment).not.toHaveBeenCalled()
  })

  it('deletes through the shared endpoint', async () => {
    wrap(<AttachmentList target={{ kind: 'task', projectId: 'p1', taskId: 't1' }} accent="#ff8015" />)
    await screen.findByText('cohort.csv')

    fireEvent.click(screen.getByTitle('Delete attachment'))

    await waitFor(() => expect(deleteAttachment).toHaveBeenCalledWith('a1'))
  })

  it('opens a file through the API, which is the only route the browser has', async () => {
    wrap(<AttachmentList target={{ kind: 'task', projectId: 'p1', taskId: 't1' }} accent="#ff8015" />)
    const name = await screen.findByText('cohort.csv')

    fireEvent.click(name)

    await waitFor(() => expect(fetchAttachmentBlob).toHaveBeenCalledWith('a1'))
    // text/csv is viewable, so it opens in a tab rather than silently downloading.
    expect(window.open).toHaveBeenCalledWith('blob:preview', '_blank', 'noopener')
  })

  it('reports a file it could not open', async () => {
    fetchAttachmentBlob.mockRejectedValue(new Error('Could not open the file'))
    wrap(<AttachmentList target={{ kind: 'task', projectId: 'p1', taskId: 't1' }} accent="#ff8015" />)
    fireEvent.click(await screen.findByText('cohort.csv'))

    expect(await screen.findByText('Could not open the file')).toBeInTheDocument()
  })

  it('still works for an experiment entry', async () => {
    // The component was generalised; the original owner must keep working.
    listAttachments.mockResolvedValue([{ ...FILE, task_id: null, entry_id: 'e1' }])
    wrap(
      <AttachmentList
        target={{ kind: 'entry', projectId: 'p1', expId: 'x1', entryId: 'e1' }}
        accent="#10b981"
      />,
    )

    expect(await screen.findByText('cohort.csv')).toBeInTheDocument()
    expect(listAttachments).toHaveBeenCalledWith('p1', 'x1', 'e1')
    expect(listTaskAttachments).not.toHaveBeenCalled()
  })
})
