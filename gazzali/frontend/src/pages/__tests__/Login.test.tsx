import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { Login } from '../Login'

const { login } = vi.hoisted(() => ({ login: vi.fn() }))
vi.mock('../../auth', () => ({ useAuth: () => ({ login }) }))

function statusResponse(body: unknown) {
  return Promise.resolve({ json: () => Promise.resolve(body) } as Response)
}

function wrap() {
  return render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>,
  )
}

describe('Login', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
  })

  it('offers Microsoft sign-in when the provider answers', async () => {
    vi.stubGlobal('fetch', vi.fn(() => statusResponse({ configured: true, reachable: true })))
    wrap()

    expect(await screen.findByText('Sign in with Microsoft')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('says so instead of sending the user into a gateway error', async () => {
    // Live failure: the identity provider sits behind a gateway that can be down
    // while this application is healthy, and the button led to a bare 502 page.
    vi.stubGlobal('fetch', vi.fn(() => statusResponse({ configured: true, reachable: false })))
    wrap()

    const notice = await screen.findByRole('status')
    expect(notice).toHaveTextContent(/unavailable right now/i)
    // …and the password form is still there, which is the way in.
    expect(screen.getByText('PASSWORD')).toBeInTheDocument()
    expect(screen.queryByText('Sign in with Microsoft')).not.toBeInTheDocument()
  })

  it('hides the Microsoft option entirely when it is not configured', async () => {
    vi.stubGlobal('fetch', vi.fn(() => statusResponse({ configured: false, reachable: false })))
    wrap()

    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/v1/auth/oidc/status'))
    expect(screen.queryByText('Sign in with Microsoft')).not.toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('still shows the button when the status check itself fails', async () => {
    // An unreachable status endpoint says nothing about the provider.
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('offline'))))
    wrap()

    await waitFor(() => expect(fetch).toHaveBeenCalled())
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
