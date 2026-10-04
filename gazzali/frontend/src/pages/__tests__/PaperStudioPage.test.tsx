import { fireEvent, render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { PaperStudioPage } from '../PaperStudioPage'
import { api, paperApi } from '../../api'

vi.mock('../../api', () => ({
  api: { getPublication: vi.fn(), listVersions: vi.fn(), getVersion: vi.fn() },
  paperApi: { stages: vi.fn(), context: vi.fn(), outline: vi.fn(), reviewPoints: vi.fn(), snapshot: vi.fn() },
}))

function renderStudio() {
  vi.mocked(api.getPublication).mockResolvedValue({ id: 'p', title: 'My paper' } as never)
  vi.mocked(api.listVersions).mockResolvedValue([])
  vi.mocked(paperApi.stages).mockResolvedValue({ stages: { setup: true }, sections_done: [], integrity: null } as never)
  vi.mocked(paperApi.context).mockResolvedValue({ sources: { tasks: [{ id: 't1', label: 'Train model' }] }, summary: { metric_count: 0, warnings: ['⚠ No measured results'] }, snapshots: [] } as never)
  vi.mocked(paperApi.outline).mockResolvedValue({ claims: [] })
  vi.mocked(paperApi.reviewPoints).mockResolvedValue({ points: [] } as never)
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/publications/p/studio']}>
    <Routes><Route path="/publications/:id/studio" element={<PaperStudioPage />} /></Routes>
  </MemoryRouter></QueryClientProvider>)
}

describe('PaperStudioPage', () => {
  it('opens on the next step, shows what is missing, and lets you look at other steps without running them', async () => {
    renderStudio()
    expect(await screen.findByRole('heading', { name: 'Gather your results' })).toBeInTheDocument()
    expect(await screen.findByText('No measured results')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save this evidence' })).toBeEnabled()

    fireEvent.click(screen.getAllByRole('button', { name: /Plan the key points/ })[0])
    expect(screen.getByRole('heading', { name: 'Plan the key points' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Suggest key points' })).toBeDisabled()
    expect(screen.getByText('Save your evidence first.')).toBeInTheDocument()
    expect(screen.getByText(/Your next step is/)).toBeInTheDocument()
    expect(paperApi.snapshot).not.toHaveBeenCalled()
  })
})
