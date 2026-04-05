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
  mockedUseAuth.mockReturnValue({ username: 'admin', isAdmin: true, token: 'tok', login: vi.fn(), logout: vi.fn() })
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
    fireEvent.click(screen.getByText('+ NEW PROJECT'))
    expect(screen.getByPlaceholderText('Brief description (optional)…')).toBeInTheDocument()
  })
})
