// src/pages/__tests__/ProjectReportPage.test.tsx
import React from 'react'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ProjectReportPage } from '../ProjectReportPage'
import type { Task, Experiment } from '../../api'

vi.mock('../../api', () => ({
  api: {
    getProject: vi.fn().mockResolvedValue({
      id: 'p1', name: 'CRISPR Study',
      members: [
        { user_id: 'u1', username: 'alice', role: 'owner', added_at: '' },
        { user_id: 'u2', username: 'bob',   role: 'editor', added_at: '' },
      ],
      description: null, created_by: 'u1',
      created_at: '2026-01-01', archived_at: null,
    }),
    listTasks: vi.fn().mockResolvedValue([]),
    listExperiments: vi.fn().mockResolvedValue([]),
    listEntries: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('../../auth', () => ({
  useAuth: vi.fn(() => ({ username: 'alice', token: 'tok' })),
}))

vi.mock('../../theme', () => ({
  useTheme: vi.fn(() => ({ theme: 'dark' })),
}))

const MOCK_TASKS: Task[] = [
  { id: 't1', project_id: 'p1', title: 'Task A', description: null,
    assignee_id: 'u1', status: 'done', priority: 'high', deadline: null,
    session_id: null, created_by: 'u1', created_at: '', updated_at: '' },
  { id: 't2', project_id: 'p1', title: 'Task B', description: null,
    assignee_id: null, status: 'todo', priority: 'medium', deadline: null,
    session_id: null, created_by: 'u1', created_at: '', updated_at: '' },
]

const MOCK_EXP: Experiment = {
  id: 'e1', project_id: 'p1', name: 'Western Blot',
  hypothesis: 'Protein is expressed', protocol: 'Run gel', status: 'running',
  tags: ['blot'], deadline: null, created_by: 'u1',
  created_at: '2026-01-01', updated_at: '2026-01-01',
}

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/projects/p1/report']}>
        <Routes>
          <Route path="/projects/:id/report" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ProjectReportPage', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('renders project name in header', async () => {
    render(wrap(<ProjectReportPage />))
    await waitFor(() => expect(screen.getByText('CRISPR Study')).toBeInTheDocument())
  })

  it('shows 0 tasks when no tasks', async () => {
    render(wrap(<ProjectReportPage />))
    await waitFor(() => expect(screen.getAllByText('0').length).toBeGreaterThanOrEqual(1))
  })

  it('shows correct done percentage', async () => {
    const { api } = await import('../../api')
    vi.mocked(api.listTasks).mockResolvedValue(MOCK_TASKS)
    render(wrap(<ProjectReportPage />))
    await waitFor(() => expect(screen.getAllByText('50%').length).toBeGreaterThanOrEqual(1))
  })

  it('shows experiment name in table', async () => {
    const { api } = await import('../../api')
    vi.mocked(api.listExperiments).mockResolvedValue([MOCK_EXP])
    render(wrap(<ProjectReportPage />))
    await waitFor(() => expect(screen.getAllByText('Western Blot').length).toBeGreaterThanOrEqual(1))
  })

  it('shows team members', async () => {
    render(wrap(<ProjectReportPage />))
    await waitFor(() => {
      expect(screen.getByText('alice')).toBeInTheDocument()
      expect(screen.getByText('bob')).toBeInTheDocument()
    })
  })

  it('expands experiment accordion on click', async () => {
    const { api } = await import('../../api')
    vi.mocked(api.listExperiments).mockResolvedValue([MOCK_EXP])
    render(wrap(<ProjectReportPage />))
    await waitFor(() => screen.getAllByText('Western Blot'))
    const buttons = screen.getAllByRole('button')
    const accordionBtn = buttons.find(b => b.textContent?.includes('Western Blot'))
    expect(accordionBtn).toBeTruthy()
    fireEvent.click(accordionBtn!)
    await waitFor(() => expect(screen.getByText('Protein is expressed')).toBeInTheDocument())
  })

  it('renders PDF button', async () => {
    render(wrap(<ProjectReportPage />))
    await waitFor(() => expect(screen.getByText(/PDF/i)).toBeInTheDocument())
  })
})
