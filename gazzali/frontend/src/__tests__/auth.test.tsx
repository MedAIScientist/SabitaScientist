import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AuthProvider, useAuth } from '../auth'

const { me } = vi.hoisted(() => ({ me: vi.fn() }))
vi.mock('../api', () => ({ api: { me, login: vi.fn() } }))

function Probe() {
  const { username, role, isAdmin } = useAuth()
  return <div>{`${username}|${role}|${String(isAdmin)}`}</div>
}

function renderProvider() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  )
}

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
  })

  it('learns the role from the server when the session carries only a token', async () => {
    // The Microsoft sign-in callback hands back a token and nothing else. Reading
    // the role from storage made professors look like students.
    sessionStorage.setItem('pm_token', 't')
    me.mockResolvedValue({ id: 'u', username: 'kbkose', is_admin: false, role: 'professor' })

    renderProvider()

    expect(await screen.findByText('kbkose|professor|false')).toBeInTheDocument()
    expect(sessionStorage.getItem('pm_role')).toBe('professor')
    expect(sessionStorage.getItem('pm_username')).toBe('kbkose')
  })

  it('corrects a role that changed while the session stayed open', async () => {
    sessionStorage.setItem('pm_token', 't')
    sessionStorage.setItem('pm_role', 'student')
    sessionStorage.setItem('pm_username', 'kbkose')
    me.mockResolvedValue({ id: 'u', username: 'kbkose', is_admin: false, role: 'professor' })

    renderProvider()

    expect(await screen.findByText('kbkose|professor|false')).toBeInTheDocument()
  })

  it('carries the admin flag from the server too', async () => {
    sessionStorage.setItem('pm_token', 't')
    me.mockResolvedValue({ id: 'u', username: 'boss', is_admin: true, role: 'professor' })

    renderProvider()

    expect(await screen.findByText('boss|professor|true')).toBeInTheDocument()
  })

  it('does not ask without a token', async () => {
    renderProvider()
    expect(await screen.findByText('null|student|false')).toBeInTheDocument()
    expect(me).not.toHaveBeenCalled()
  })

  it('keeps the seeded identity when the server cannot be reached', async () => {
    sessionStorage.setItem('pm_token', 't')
    sessionStorage.setItem('pm_role', 'professor')
    sessionStorage.setItem('pm_username', 'kbkose')
    me.mockRejectedValue(new Error('network down'))

    renderProvider()

    await waitFor(() => expect(me).toHaveBeenCalled())
    expect(screen.getByText('kbkose|professor|false')).toBeInTheDocument()
  })
})
