import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi, beforeEach } from 'vitest'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth'
import { ProjectSettingsPanel } from '../ProjectSettingsPanel'
import type { Project } from '../../api'

vi.mock('@tanstack/react-query', () => ({
  useMutation: vi.fn(),
  useQueryClient: vi.fn(),
}))
vi.mock('react-router-dom', () => ({
  useNavigate: vi.fn(),
}))
vi.mock('../../auth', () => ({
  useAuth: vi.fn(),
}))
vi.mock('../../api', () => ({
  api: {
    updateProject: vi.fn(),
    deleteProject: vi.fn(),
    updateMemberRole: vi.fn(),
    removeMember: vi.fn(),
    addMember: vi.fn(),
    searchUsers: vi.fn(() => Promise.resolve([])),
  },
}))

const mockedUseMutation = vi.mocked(useMutation)
const mockedUseQueryClient = vi.mocked(useQueryClient)
const mockedUseNavigate = vi.mocked(useNavigate)
const mockedUseAuth = vi.mocked(useAuth)

const MOCK_PROJECT: Project = {
  id: 'proj-1',
  name: 'CRISPR Study',
  description: 'Gene editing experiments',
  created_by: 'u1',
  created_at: '2024-01-01T00:00:00Z',
  archived_at: null,
  members: [
    { user_id: 'u1', username: 'dr_chen', role: 'owner', added_at: '2024-01-01T00:00:00Z' },
    { user_id: 'u2', username: 'lab_tech', role: 'editor', added_at: '2024-01-01T00:00:00Z' },
  ],
}

function renderPanel(onClose = vi.fn()) {
  return render(
    <ProjectSettingsPanel
      project={MOCK_PROJECT}
      projectId="proj-1"
      onClose={onClose}
    />
  )
}

beforeEach(() => {
  mockedUseAuth.mockReturnValue({ username: 'dr_chen', isAdmin: false, token: 'tok', login: vi.fn(), logout: vi.fn() })
  mockedUseNavigate.mockReturnValue(vi.fn())
  mockedUseQueryClient.mockReturnValue({ invalidateQueries: vi.fn() } as any)
  mockedUseMutation.mockReturnValue({ mutate: vi.fn(), isPending: false } as any)
})

describe('ProjectSettingsPanel', () => {
  test('renders PROJECT SETTINGS title', () => {
    renderPanel()
    expect(screen.getByText('PROJECT SETTINGS')).toBeInTheDocument()
  })

  test('renders project name input pre-filled', () => {
    renderPanel()
    expect(screen.getByDisplayValue('CRISPR Study')).toBeInTheDocument()
  })

  test('renders description textarea pre-filled', () => {
    renderPanel()
    expect(screen.getByDisplayValue('Gene editing experiments')).toBeInTheDocument()
  })

  test('renders both member usernames', () => {
    renderPanel()
    expect(screen.getByText('dr_chen')).toBeInTheDocument()
    expect(screen.getByText('lab_tech')).toBeInTheDocument()
  })

  test('clicking DELETE PROJECT once shows CONFIRM DELETE ?', () => {
    renderPanel()
    const deleteBtn = screen.getByRole('button', { name: /delete project/i })
    fireEvent.click(deleteBtn)
    expect(screen.getByRole('button', { name: /confirm delete/i })).toBeInTheDocument()
  })

  test('self member row (dr_chen) has remove button disabled', () => {
    renderPanel()
    const removeButtons = screen.getAllByRole('button', { name: /✕/ })
    // dr_chen is first member; its remove button should be disabled
    expect(removeButtons[0]).toBeDisabled()
  })

  test('other member row (lab_tech) has remove button enabled', () => {
    renderPanel()
    const removeButtons = screen.getAllByRole('button', { name: /✕/ })
    expect(removeButtons[1]).not.toBeDisabled()
  })

  test('renders ADD RESEARCHER username search input', () => {
    renderPanel()
    expect(screen.getByPlaceholderText('Search by username…')).toBeInTheDocument()
  })
})
