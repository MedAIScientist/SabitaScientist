import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi, beforeEach } from 'vitest'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { GrantsPage } from '../GrantsPage'
import { ConferencesPage } from '../ConferencesPage'
import { IRBPage } from '../IRBPage'

vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
  useQueryClient: vi.fn(),
}))
vi.mock('react-router-dom', () => ({
  useNavigate: vi.fn(),
}))

const mockedUseQuery = vi.mocked(useQuery)
const mockedUseMutation = vi.mocked(useMutation)
const mockedUseQueryClient = vi.mocked(useQueryClient)
const mockedUseNavigate = vi.mocked(useNavigate)

beforeEach(() => {
  mockedUseNavigate.mockReturnValue(vi.fn())
  mockedUseQueryClient.mockReturnValue({ invalidateQueries: vi.fn() } as any)
  mockedUseMutation.mockReturnValue({ mutate: vi.fn(), isPending: false } as any)
  mockedUseQuery.mockReturnValue({ data: [], isLoading: false } as any)
})

describe('GrantsPage', () => {
  test('renders Grants heading', () => {
    render(<GrantsPage />)
    expect(screen.getByText('Grants')).toBeInTheDocument()
  })

  test('create form reveals title/funder fields on + NEW', () => {
    render(<GrantsPage />)
    fireEvent.click(screen.getByText('+ NEW'))
    expect(screen.getByPlaceholderText('Project title')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('TÜBİTAK, TÜSEB, etc.')).toBeInTheDocument()
  })
})

describe('ConferencesPage', () => {
  test('renders Conferences heading', () => {
    render(<ConferencesPage />)
    expect(screen.getByText('Conferences')).toBeInTheDocument()
  })

  test('create form reveals conference name field on + NEW', () => {
    render(<ConferencesPage />)
    fireEvent.click(screen.getByText('+ NEW'))
    expect(screen.getByPlaceholderText('Conference name')).toBeInTheDocument()
  })
})

describe('IRBPage', () => {
  test('renders IRB heading', () => {
    render(<IRBPage />)
    expect(screen.getByText('IRB / Ethics Approvals')).toBeInTheDocument()
  })

  test('create form reveals protocol fields on + NEW', () => {
    render(<IRBPage />)
    fireEvent.click(screen.getByText('+ NEW'))
    expect(screen.getByPlaceholderText('Protocol title')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Protocol #')).toBeInTheDocument()
  })
})
