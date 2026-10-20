import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { UsersPage } from '../UsersPage'

vi.mock('../../api', () => ({ api: { listUsers: vi.fn(), createUser: vi.fn() } }))
vi.mock('../../auth', () => ({ useAuth: () => ({ isAdmin: true }) }))
import { api } from '../../api'
const mocked = vi.mocked(api)

beforeEach(() => {
  vi.resetAllMocks()
  mocked.listUsers.mockResolvedValue([] as never)
  mocked.createUser.mockResolvedValue({} as never)
})

async function createAs(role: string) {
  render(<MemoryRouter><UsersPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: '+ Add user' }))
  fireEvent.change(screen.getByPlaceholderText('username'), { target: { value: 'root2' } })
  fireEvent.change(screen.getByPlaceholderText('••••••••'), { target: { value: 'Secret123' } })
  fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: role } })
  fireEvent.click(screen.getByRole('button', { name: 'Create' }))
  await waitFor(() => expect(mocked.createUser).toHaveBeenCalled())
}

describe('UsersPage — creating an admin', () => {
  it('choosing the admin role also sets is_admin, which is what the server checks', async () => {
    await createAs('admin')
    expect(mocked.createUser).toHaveBeenCalledWith('root2', 'Secret123', undefined, 'admin', true)
  })

  it('any other role creates a non-admin', async () => {
    await createAs('professor')
    expect(mocked.createUser).toHaveBeenCalledWith('root2', 'Secret123', undefined, 'professor', false)
  })
})
