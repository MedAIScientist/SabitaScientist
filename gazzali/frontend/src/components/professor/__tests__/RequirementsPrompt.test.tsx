import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { RequirementsPrompt } from '../RequirementsPrompt'
import { supervisionApi } from '../../../api'

vi.mock('../../../api', () => ({ supervisionApi: { studentsOverview: vi.fn(), listRequirements: vi.fn() } }))

const show = () => render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><RequirementsPrompt /></MemoryRouter></QueryClientProvider>)

describe('RequirementsPrompt', () => {
  beforeEach(() => sessionStorage.clear())

  it('names the student levels that have no requirements', async () => {
    vi.mocked(supervisionApi.studentsOverview).mockResolvedValue([{ level: 'phd' }, { level: 'phd' }, { level: 'MSc' }, { level: null }] as never)
    vi.mocked(supervisionApi.listRequirements).mockResolvedValue([{ level: 'MSc' }] as never)
    show()
    expect(await screen.findByText(/phd \(2 students\)/)).toBeInTheDocument()
    expect(screen.queryByText(/MSc/)).not.toBeInTheDocument()
  })

  it('stays hidden when every level is covered', async () => {
    vi.mocked(supervisionApi.studentsOverview).mockResolvedValue([{ level: 'PhD' }] as never)
    vi.mocked(supervisionApi.listRequirements).mockResolvedValue([{ level: 'PhD' }] as never)
    const { container } = show()
    await new Promise(r => setTimeout(r, 20))
    expect(container).toBeEmptyDOMElement()
  })
})
