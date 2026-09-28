import { render, screen } from '@testing-library/react'
import { describe, test, expect, vi, beforeEach } from 'vitest'
import { useQuery } from '@tanstack/react-query'
import { AppsPage } from '../AppsPage'

vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(),
}))

const mockedUseQuery = vi.mocked(useQuery)

const cvat = {
  key: 'cvat', name: 'CVAT', path: '/cvat/', kind: 'annotation' as const,
  description: 'Annotate images and video.', up: true, http_status: 200, latency_ms: 42,
}
const curator = {
  key: 'curator', name: 'Curator', path: '/pacs/', kind: 'imaging' as const,
  description: 'Search the PACS archive.', up: false, http_status: 502, latency_ms: 15,
}

beforeEach(() => {
  mockedUseQuery.mockReturnValue({
    data: [cvat, curator], isLoading: false, isFetching: false,
    refetch: vi.fn(), error: null,
  } as any)
})

describe('AppsPage', () => {
  test('lists each companion app with its subpath', () => {
    render(<AppsPage />)
    expect(screen.getByText('CVAT')).toBeInTheDocument()
    expect(screen.getByText('/cvat/')).toBeInTheDocument()
    expect(screen.getByText('Curator')).toBeInTheDocument()
    expect(screen.getByText('/pacs/')).toBeInTheDocument()
  })

  test('shows per-service UP/DOWN state', () => {
    render(<AppsPage />)
    expect(screen.getByText('UP')).toBeInTheDocument()
    expect(screen.getByText('DOWN')).toBeInTheDocument()
  })

  test('names the unreachable service with its status', () => {
    render(<AppsPage />)
    expect(screen.getByText('UNREACHABLE (HTTP 502)')).toBeInTheDocument()
  })

  test('counts unreachable services in the header', () => {
    render(<AppsPage />)
    expect(screen.getByText(/2 SERVICES/)).toBeInTheDocument()
    expect(screen.getByText(/1 UNREACHABLE/)).toBeInTheDocument()
  })

  test('every card opens its app in a new tab', () => {
    render(<AppsPage />)
    const links = screen.getAllByRole('link')
    const hrefs = links.map(l => l.getAttribute('href'))
    expect(hrefs).toContain('/cvat/')
    expect(hrefs).toContain('/pacs/')
    for (const link of links) {
      expect(link).toHaveAttribute('target', '_blank')
      // reverse-tabnabbing guard
      expect(link.getAttribute('rel')).toContain('noopener')
    }
  })

  test('renders a loading state before the first probe returns', () => {
    mockedUseQuery.mockReturnValue({
      data: [], isLoading: true, isFetching: true, refetch: vi.fn(), error: null,
    } as any)
    render(<AppsPage />)
    expect(screen.getByText('LOADING…')).toBeInTheDocument()
  })

  test('reports a failed status read without hiding the page', () => {
    mockedUseQuery.mockReturnValue({
      data: [], isLoading: false, isFetching: false, refetch: vi.fn(),
      error: new Error('boom'),
    } as any)
    render(<AppsPage />)
    expect(screen.getByText(/Could not read service status/)).toBeInTheDocument()
  })
})
