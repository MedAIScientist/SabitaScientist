import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { DatasetRequestDialog } from '../DatasetRequestDialog'

vi.mock('../../../api', () => ({
  api: { listIrbs: vi.fn(), listLabs: vi.fn(), requestDataset: vi.fn(), listCuratorSelections: vi.fn() },
}))
import { api, type Project } from '../../../api'
const mocked = vi.mocked(api)

const project = {
  id: 'p1', name: 'test-project', description: null, created_by: 'u1', created_at: '', archived_at: null,
  members: [], lab_id: 'l1',
} as Project
const irb = (over: Record<string, unknown>) => ({
  id: 'i1', title: 'Ankle DX study', institution: 'Medipol', protocol_number: 'E-1',
  status: 'approved', approval_date: '2026-10-01', expiry_date: '2099-01-01', ...over,
})

function renderDialog() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}><MemoryRouter>
      <DatasetRequestDialog project={project} onClose={() => {}} />
    </MemoryRouter></QueryClientProvider>,
  )
}

const SEL = 'sel_' + 'a'.repeat(32)
const selection = (over: Record<string, unknown> = {}) => ({
  id: SEL, name: 'DX ayak bilek 2019', created_at: '2026-10-17T08:00:00Z', expires_at: '2026-11-16T08:00:00Z',
  studies: 12, patients: 11, instances: 130, instances_unknown: 0, modalities: ['DX'],
  date_from: '2019-01-01', date_to: '2019-12-31', modality: 'DX', renders: false,
  status: 'pending', submitted_at: null, medai_dataset_id: null, ...over,
})

async function fillRequired() {
  fireEvent.click(await screen.findByRole('radio', { name: /DX ayak bilek 2019/ }))
  fireEvent.change(screen.getByPlaceholderText(/reviewers read this/), { target: { value: 'Fracture study' } })
}

beforeEach(() => {
  vi.resetAllMocks()
  mocked.listLabs.mockResolvedValue([{ id: 'l1', name: 'test-lab', members: [{ user_id: 'u1' }], can_manage: true }] as never)
  mocked.requestDataset.mockResolvedValue({} as never)
  mocked.listCuratorSelections.mockResolvedValue({ selections: [selection()] } as never)
})

describe('DatasetRequestDialog — no request without an ethics record', () => {
  it('cannot be sent until an IRB is ticked, then sends it', async () => {
    mocked.listIrbs.mockResolvedValue([irb({})] as never)
    renderDialog()
    await screen.findByText('Ankle DX study')
    await fillRequired()
    const send = screen.getByRole('button', { name: 'Send request' })
    expect(send).toBeDisabled()
    fireEvent.click(screen.getByRole('checkbox', { name: /Ankle DX study/ }))
    expect(send).toBeEnabled()
    fireEvent.click(send)
    await waitFor(() => expect(mocked.requestDataset).toHaveBeenCalled())
    expect(mocked.requestDataset.mock.calls[0][0]).toMatchObject({ irb_ids: ['i1'], curator_selection_id: SEL })
  })

  it('a project with no IRB links straight to creating one for that project', async () => {
    mocked.listIrbs.mockResolvedValue([] as never)
    renderDialog()
    const link = await screen.findByRole('link', { name: /Add an ethics record for this project/ })
    expect(link).toHaveAttribute('href', '/irb?project=p1')
    await fillRequired()
    expect(screen.getByRole('button', { name: 'Send request' })).toBeDisabled()
  })

  it('a closed IRB cannot be ticked', async () => {
    mocked.listIrbs.mockResolvedValue([irb({ status: 'closed' })] as never)
    renderDialog()
    expect(await screen.findByRole('checkbox', { name: /Ankle DX study/ })).toBeDisabled()
  })
})

describe('DatasetRequestDialog — the studies come from a saved Curator selection', () => {
  it('sends the selection, never an accession list, and has nowhere to type one', async () => {
    mocked.listIrbs.mockResolvedValue([irb({})] as never)
    renderDialog()
    await fillRequired()
    fireEvent.click(screen.getByRole('checkbox', { name: /Ankle DX study/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Send request' }))
    await waitFor(() => expect(mocked.requestDataset).toHaveBeenCalled())
    const sent = mocked.requestDataset.mock.calls[0][0] as Record<string, unknown>
    expect(sent.curator_selection_id).toBe(SEL)
    expect(sent).not.toHaveProperty('accession_list')
    expect(screen.queryByPlaceholderText(/One per line/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Accession numbers/)).not.toBeInTheDocument()
  })

  it('choosing a selection fills the name, modality and the viewable-images choice from it', async () => {
    mocked.listIrbs.mockResolvedValue([irb({})] as never)
    renderDialog()
    await fillRequired()
    expect(screen.getByPlaceholderText(/Knee MR/)).toHaveValue('DX ayak bilek 2019')
    expect(screen.getByRole('checkbox', { name: /Also create viewable images/ })).not.toBeChecked()
    expect(screen.getByText(/12 studies · DX · 2019-01-01 → 2019-12-31/)).toBeInTheDocument()
  })

  it('a selection already requested is shown but cannot be chosen again', async () => {
    mocked.listIrbs.mockResolvedValue([irb({})] as never)
    mocked.listCuratorSelections.mockResolvedValue({ selections: [selection({ status: 'submitted', medai_dataset_id: 'f'.repeat(32) })] } as never)
    renderDialog()
    expect(await screen.findByRole('radio', { name: /DX ayak bilek 2019/ })).toBeDisabled()
    expect(screen.getByText(/already requested/)).toBeInTheDocument()
  })

  it('with nothing saved yet it says how to save one in Curator', async () => {
    mocked.listIrbs.mockResolvedValue([irb({})] as never)
    mocked.listCuratorSelections.mockResolvedValue({ selections: [] } as never)
    renderDialog()
    expect(await screen.findByText(/no saved selections yet/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Curator' })).toHaveAttribute('href', '/pacs')
    expect(screen.getByRole('button', { name: 'Send request' })).toBeDisabled()
  })

  it("when Curator cannot be reached it says so instead of offering a manual list", async () => {
    mocked.listIrbs.mockResolvedValue([irb({})] as never)
    mocked.listCuratorSelections.mockRejectedValue(new Error('Curator could not be reached; try again'))
    renderDialog()
    expect(await screen.findByRole('alert')).toHaveTextContent('Curator could not be reached')
    expect(screen.getByRole('button', { name: 'Send request' })).toBeDisabled()
  })
})
