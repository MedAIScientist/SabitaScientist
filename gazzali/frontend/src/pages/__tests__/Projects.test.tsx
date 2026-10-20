import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi, beforeEach } from 'vitest'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth'
import { Projects } from '../Projects'

vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
  useQueryClient: vi.fn(),
}))
vi.mock('react-router-dom', () => ({
  useNavigate: vi.fn(),
}))
vi.mock('../../auth', () => ({
  useAuth: vi.fn(),
}))

const mockedUseQuery = vi.mocked(useQuery)
const mockedUseMutation = vi.mocked(useMutation)
const mockedUseQueryClient = vi.mocked(useQueryClient)
const mockedUseNavigate = vi.mocked(useNavigate)
const mockedUseAuth = vi.mocked(useAuth)

beforeEach(() => {
  mockedUseAuth.mockReturnValue({ username: 'admin', isAdmin: true, role: 'admin', token: 'tok', login: vi.fn(), logout: vi.fn() })
  mockedUseNavigate.mockReturnValue(vi.fn())
  mockedUseQueryClient.mockReturnValue({ invalidateQueries: vi.fn() } as any)
  mockedUseMutation.mockReturnValue({ mutate: vi.fn(), isPending: false } as any)
  mockedUseQuery.mockReturnValue({ data: [], isLoading: false } as any)
})

describe('Projects', () => {
  test('renders Research Projects heading', () => {
    render(<Projects />)
    expect(screen.getByText('Research Projects')).toBeInTheDocument()
  })

  test('description textarea appears in create form when creating', () => {
    render(<Projects />)
    fireEvent.click(screen.getByText('+ New project'))
    expect(screen.getByPlaceholderText('Brief description (optional)')).toBeInTheDocument()
  })

  describe('choosing the lab at creation', () => {
    const lab = (id: string, name: string, members: unknown[]) => ({ id, name, members }) as any
    function withLabs(labs: unknown[]) {
      mockedUseQuery.mockImplementation(((opts: { queryKey: unknown[] }) =>
        opts.queryKey[0] === 'labs' ? { data: labs, isLoading: false } : { data: [], isLoading: false }) as any)
      const mutate = vi.fn()
      mockedUseMutation.mockReturnValue({ mutate, isPending: false, isError: false } as any)
      render(<Projects />)
      fireEvent.click(screen.getByText('+ New project'))
      fireEvent.change(screen.getByPlaceholderText('Project name'), { target: { value: 'Ankle study' } })
      return mutate
    }
    const submit = () => fireEvent.click(screen.getByRole('button', { name: 'Create' }))

    test('the only lab the user is in is preselected and sent', () => {
      const mutate = withLabs([lab('L1', 'Test Lab', [{ user_id: 'u1' }])])
      expect(screen.getByLabelText('Lab')).toHaveValue('L1')
      submit()
      expect(mutate).toHaveBeenCalledWith(expect.objectContaining({ name: 'Ankle study', labId: 'L1' }))
    })

    test('labs whose roster is hidden (the user is not in them) are not offered', () => {
      withLabs([lab('L1', 'Test Lab', [{ user_id: 'u1' }]), lab('L2', 'Other Lab', [])])
      expect(screen.queryByRole('option', { name: 'Other Lab' })).not.toBeInTheDocument()
    })

    test('"No lab" can be chosen over the preselected lab', () => {
      const mutate = withLabs([lab('L1', 'Test Lab', [{ user_id: 'u1' }])])
      fireEvent.change(screen.getByLabelText('Lab'), { target: { value: '' } })
      submit()
      expect(mutate).toHaveBeenCalledWith(expect.objectContaining({ labId: undefined }))
    })

    test('with several labs nothing is preselected; the picked one is sent', () => {
      const mutate = withLabs([lab('L1', 'Test Lab', [{ user_id: 'u1' }]), lab('L2', 'Bone Lab', [{ user_id: 'u1' }])])
      expect(screen.getByLabelText('Lab')).toHaveValue('')
      fireEvent.change(screen.getByLabelText('Lab'), { target: { value: 'L2' } })
      submit()
      expect(mutate).toHaveBeenCalledWith(expect.objectContaining({ labId: 'L2' }))
    })

    test('a user in no lab sees no lab picker', () => {
      withLabs([])
      expect(screen.queryByLabelText('Lab')).not.toBeInTheDocument()
    })
  })
})
