import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DatasetRequests } from '../DatasetRequests'

vi.mock('../../../api', () => ({ api: { listDatasetRequests: vi.fn() } }))
import { api } from '../../../api'
const mocked = vi.mocked(api)

const ID = '0123456789abcdef0123456789abcdef'
const request = {
  id: ID, name: 'DX ayak bilek 2019', modality: 'DX', purpose: 'Fracture study', status: 'approved',
  requested_by: 'student1', accession_count: 12, created_at: '2026-10-16T10:00:00Z',
  steps: [{ key: 'irb', label: 'Ethics', state: 'done' }], waiting_on: 'Platform admin (deliver the images)', irbs: [],
}

function renderTracker() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}><DatasetRequests projectId="p1" /></QueryClientProvider>)
}

beforeEach(() => {
  vi.resetAllMocks()
  mocked.listDatasetRequests.mockResolvedValue([request] as never)
})

describe('DatasetRequests — the dataset id', () => {
  it('shows the whole id, which is what Curator lists the cohort by', async () => {
    renderTracker()
    expect(await screen.findByTitle('Dataset id')).toHaveTextContent(ID)
  })

  it('copies exactly the id', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    renderTracker()
    fireEvent.click(await screen.findByRole('button', { name: 'Copy dataset id' }))
    expect(writeText).toHaveBeenCalledWith(ID)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Copy dataset id' })).toHaveTextContent('Copied'))
  })

  it('without a clipboard (plain http) the id is still on screen to select by hand', async () => {
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
    renderTracker()
    fireEvent.click(await screen.findByRole('button', { name: 'Copy dataset id' }))
    expect(screen.getByTitle('Dataset id')).toHaveTextContent(ID)
  })
})
