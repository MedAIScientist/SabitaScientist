import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { CompanionStatusBanner } from '../CompanionStatusBanner'

const { listIntegrations } = vi.hoisted(() => ({ listIntegrations: vi.fn() }))
vi.mock('../../api', () => ({ api: { listIntegrations } }))

function app(key: string, name: string, up: boolean) {
  return { key, name, path: `/${key}/`, kind: 'compute', description: '', up, http_status: up ? 200 : 502, latency_ms: 10 }
}

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <CompanionStatusBanner />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('CompanionStatusBanner', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
  })

  it('stays out of the way when everything answers', async () => {
    listIntegrations.mockResolvedValue([app('cvat', 'CVAT', true), app('jupyter', 'JupyterHub', true)])
    wrap()

    await waitFor(() => expect(listIntegrations).toHaveBeenCalled())
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('names the services that are down instead of letting users find a 502', async () => {
    // The live failure: the cluster gateway stopped answering and the first anyone
    // heard of it was a user complaint.
    listIntegrations.mockResolvedValue([app('cvat', 'CVAT', false), app('jupyter', 'JupyterHub', false)])
    wrap()

    const banner = await screen.findByRole('status')
    expect(banner).toHaveTextContent('2 companion services are not answering')
    expect(banner).toHaveTextContent('CVAT, JupyterHub')
    // And it says whose problem it is not.
    expect(banner).toHaveTextContent('not a problem with your account')
    expect(screen.getByRole('link', { name: /system health/i })).toHaveAttribute('href', '/health')
  })

  it('uses the singular when only one is down', async () => {
    listIntegrations.mockResolvedValue([app('cvat', 'CVAT', false), app('jupyter', 'JupyterHub', true)])
    wrap()

    expect(await screen.findByRole('status')).toHaveTextContent('CVAT is not answering')
  })

  it('can be dismissed, and stays dismissed while the same thing is broken', async () => {
    listIntegrations.mockResolvedValue([app('cvat', 'CVAT', false)])
    const { unmount } = wrap()

    fireEvent.click(await screen.findByLabelText('Dismiss'))
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
    expect(sessionStorage.getItem('pm_companion_down_dismissed')).toBe('cvat')

    // A remount within the session must not resurrect it.
    unmount()
    wrap()
    await waitFor(() => expect(listIntegrations).toHaveBeenCalledTimes(2))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('speaks up again when a different service breaks', async () => {
    sessionStorage.setItem('pm_companion_down_dismissed', 'cvat')
    listIntegrations.mockResolvedValue([app('cvat', 'CVAT', false), app('pacs', 'Curator', false)])
    wrap()

    // The signature changed, so the earlier dismissal no longer applies.
    expect(await screen.findByRole('status')).toHaveTextContent('CVAT, Curator')
  })
})
