import React from 'react'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { IRBPage } from '../IRBPage'

vi.mock('../../api', () => ({
  api: { listIrbs: vi.fn(), listProjects: vi.fn(), listLabs: vi.fn(), createIrb: vi.fn(), updateIrb: vi.fn() },
}))
const auth = { isAdmin: false, username: 'pi1' }
vi.mock('../../auth', () => ({ useAuth: () => auth }))

import { api } from '../../api'
const mocked = vi.mocked(api)

const project = {
  id: 'p1', name: 'test-project', description: null, created_by: 'u1', created_at: '', archived_at: null,
  members: [{ user_id: 'u1', username: 'pi1', role: 'owner', added_at: '' }], lab_id: null,
}
const irb = (over: Record<string, unknown>) => ({
  id: 'i1', project_id: 'p1', title: 'Ankle DX study', institution: 'Medipol', protocol_number: 'E-1',
  status: 'draft', approval_date: null, expiry_date: null, documents: [], notes: null, ...over,
})

function renderPage(entry = '/irb') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}><MemoryRouter initialEntries={[entry]}><IRBPage /></MemoryRouter></QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.resetAllMocks()
  Object.assign(auth, { isAdmin: false, username: 'pi1' })
  mocked.listProjects.mockResolvedValue([project] as never)
  mocked.listLabs.mockResolvedValue([] as never)
  mocked.updateIrb.mockResolvedValue({} as never)
})

describe('IRBPage — the lifecycle without a console', () => {
  it('the project owner submits a draft with the committee evidence in one step', async () => {
    mocked.listIrbs.mockResolvedValue([irb({})] as never)
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Submit for review' }))
    const form = screen.getByRole('form', { name: 'Submit for review' })
    fireEvent.change(within(form).getByLabelText('Committee decision date'), { target: { value: '2026-10-01' } })
    fireEvent.change(within(form).getByLabelText('Valid until'), { target: { value: '2099-10-01' } })
    fireEvent.change(within(form).getByLabelText(/Document references/), { target: { value: 'EK-2026/14\n' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Submit for review' }))
    await waitFor(() => expect(mocked.updateIrb).toHaveBeenCalledWith('i1', {
      status: 'submitted', approval_date: '2026-10-01', expiry_date: '2099-10-01', documents: ['EK-2026/14'],
    }))
  })

  it('the submit button stays disabled until the evidence would be accepted', async () => {
    mocked.listIrbs.mockResolvedValue([irb({})] as never)
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Submit for review' }))
    const form = screen.getByRole('form', { name: 'Submit for review' })
    expect(within(form).getByRole('button', { name: 'Submit for review' })).toBeDisabled()
    expect(within(form).getByText('Add at least one document reference.')).toBeInTheDocument()
  })

  it('a writer is never offered a decision; only the admin sees Approve and Reject', async () => {
    mocked.listIrbs.mockResolvedValue([irb({ status: 'submitted' })] as never)
    const { unmount } = renderPage()
    expect(await screen.findByRole('button', { name: 'Withdraw' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Approve…' })).toBeNull()
    unmount()
    Object.assign(auth, { isAdmin: true, username: 'admin' })
    renderPage()
    expect(await screen.findByRole('button', { name: 'Approve…' })).toBeInTheDocument()
    expect(screen.getByText(/1 awaiting your decision/)).toBeInTheDocument()
  })

  it('the admin approves with the evidence pre-filled from the submission', async () => {
    Object.assign(auth, { isAdmin: true, username: 'admin' })
    mocked.listIrbs.mockResolvedValue([irb({
      status: 'submitted', approval_date: '2026-10-01', expiry_date: '2099-10-01', documents: ['EK-2026/14'],
    })] as never)
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Approve…' }))
    fireEvent.click(within(screen.getByRole('form', { name: 'Approve' })).getByRole('button', { name: 'Approve' }))
    await waitFor(() => expect(mocked.updateIrb).toHaveBeenCalledWith('i1', {
      status: 'approved', approval_date: '2026-10-01', expiry_date: '2099-10-01', documents: ['EK-2026/14'],
    }))
  })

  it('a rejection needs a reason and keeps the earlier notes', async () => {
    Object.assign(auth, { isAdmin: true, username: 'admin' })
    mocked.listIrbs.mockResolvedValue([irb({ status: 'submitted', notes: 'first note' })] as never)
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Reject…' }))
    const form = screen.getByRole('form', { name: 'Reject' })
    expect(within(form).getByRole('button', { name: 'Reject' })).toBeDisabled()
    fireEvent.change(within(form).getByLabelText(/Reason/), { target: { value: 'decision letter missing' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Reject' }))
    await waitFor(() => expect(mocked.updateIrb).toHaveBeenCalled())
    const [, body] = mocked.updateIrb.mock.calls[0] as [string, { status: string; notes: string }]
    expect(body.status).toBe('rejected')
    expect(body.notes).toMatch(/^first note\n\nRejected \d{4}-\d{2}-\d{2}: decision letter missing$/)
  })

  it("the server's refusal is shown, not swallowed", async () => {
    mocked.listIrbs.mockResolvedValue([irb({ status: 'submitted' })] as never)
    mocked.updateIrb.mockRejectedValue(new Error('IRB records require write on the referenced project'))
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Withdraw' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('IRB records require write on the referenced project')
  })

  it('an approved record past its validity is flagged LAPSED and offers a writer nothing', async () => {
    mocked.listIrbs.mockResolvedValue([irb({ status: 'approved', approval_date: '2020-01-01', expiry_date: '2021-01-01', documents: ['x'] })] as never)
    renderPage()
    expect(await screen.findByText('LAPSED')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Mark expired|Close|Submit/ })).toBeNull()
  })

  it('creating needs a chosen project and sends its id — never an empty one', async () => {
    mocked.listIrbs.mockResolvedValue([] as never)
    mocked.createIrb.mockResolvedValue({} as never)
    renderPage('/irb?project=p1')
    const form = await screen.findByRole('form', { name: 'New ethics record' })
    await waitFor(() => expect(within(form).getByLabelText('Project')).toHaveValue('p1'))
    fireEvent.change(within(form).getByLabelText('Protocol title'), { target: { value: 'Ankle DX study' } })
    fireEvent.change(within(form).getByLabelText('Institution'), { target: { value: 'Medipol' } })
    fireEvent.change(within(form).getByLabelText('Protocol number'), { target: { value: 'E-1' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save draft' }))
    await waitFor(() => expect(mocked.createIrb).toHaveBeenCalledWith({
      project_id: 'p1', title: 'Ankle DX study', institution: 'Medipol', protocol_number: 'E-1',
    }))
  })
})
