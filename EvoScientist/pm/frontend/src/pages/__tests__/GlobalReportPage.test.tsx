// src/pages/__tests__/GlobalReportPage.test.tsx
import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { GlobalReportPage } from '../GlobalReportPage'
import type { Project, Task, Experiment } from '../../api'

const MOCK_PROJECTS: Project[] = [
  {
    id: 'p1', name: 'CRISPR Study', description: null,
    created_by: 'u1', created_at: '2026-01-01', archived_at: null,
    members: [{ user_id: 'u1', username: 'alice', role: 'owner', added_at: '' }],
  },
  {
    id: 'p2', name: 'Proteomics', description: null,
    created_by: 'u1', created_at: '2026-01-02', archived_at: null,
    members: [{ user_id: 'u1', username: 'alice', role: 'owner', added_at: '' }],
  },
]

const MOCK_TASKS_P1: Task[] = [
  { id: 't1', project_id: 'p1', title: 'Task A', description: null,
    assignee_id: null, status: 'done', priority: 'high', deadline: null,
    session_id: null, created_by: 'u1', created_at: '', updated_at: '' },
]

const MOCK_EXP: Experiment = {
  id: 'e1', project_id: 'p1', name: 'Western Blot', hypothesis: null,
  protocol: null, status: 'running', tags: [], deadline: null,
  created_by: 'u1', created_at: '2026-01-01', updated_at: '2026-01-01',
}

vi.mock('../../api', () => ({
  api: {
    listProjects: vi.fn().mockResolvedValue([]),
    listTasks: vi.fn().mockResolvedValue([]),
    listExperiments: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('../../theme', () => ({
  useTheme: vi.fn(() => ({ theme: 'dark' })),
}))

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/reports']}>
        <Routes>
          <Route path="/reports" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('GlobalReportPage', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('renders reports heading', async () => {
    render(wrap(<GlobalReportPage />))
    await waitFor(() => expect(screen.getByText('reports')).toBeInTheDocument())
  })

  it('shows 0 total projects with empty list', async () => {
    render(wrap(<GlobalReportPage />))
    await waitFor(() => expect(screen.getByText('0')).toBeInTheDocument())
  })

  it('shows project names when projects exist', async () => {
    const { api } = await import('../../api')
    vi.mocked(api.listProjects).mockResolvedValue(MOCK_PROJECTS)
    vi.mocked(api.listTasks).mockImplementation((id) =>
      Promise.resolve(id === 'p1' ? MOCK_TASKS_P1 : [])
    )
    vi.mocked(api.listExperiments).mockImplementation((id) =>
      Promise.resolve(id === 'p1' ? [MOCK_EXP] : [])
    )
    render(wrap(<GlobalReportPage />))
    await waitFor(() => {
      expect(screen.getByText('CRISPR Study')).toBeInTheDocument()
      expect(screen.getByText('Proteomics')).toBeInTheDocument()
    })
  })

  it('shows VIEW REPORT links for each project', async () => {
    const { api } = await import('../../api')
    vi.mocked(api.listProjects).mockResolvedValue(MOCK_PROJECTS)
    vi.mocked(api.listTasks).mockResolvedValue([])
    vi.mocked(api.listExperiments).mockResolvedValue([])
    render(wrap(<GlobalReportPage />))
    await waitFor(() => {
      const links = screen.getAllByText(/VIEW REPORT/)
      expect(links.length).toBe(2)
    })
  })
})
