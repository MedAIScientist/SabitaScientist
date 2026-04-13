// EvoScientist/pm/frontend/src/pages/__tests__/TaskDetail.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi, beforeEach } from 'vitest'

// ── TanStack Query mocks ──────────────────────────────────────────────────────
const mockInvalidateQueries = vi.fn()
const mockMutate = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
  useQueryClient: vi.fn(() => ({ invalidateQueries: mockInvalidateQueries })),
}))

// ── Child component mocks ─────────────────────────────────────────────────────
vi.mock('../../components/task/TaskDetailView', () => ({
  TaskDetailView: ({ task }: { task: { title: string; blocked_by?: string[] } }) => (
    <div data-testid="details-tab">
      <span>{task.title}</span>
      {task.blocked_by?.length ? <span>BLOCKED</span> : null}
    </div>
  ),
}))

vi.mock('../../components/task/LabNotesTab', () => ({
  LabNotesTab: () => <div data-testid="notes-tab">Notes</div>,
}))

vi.mock('../../components/task/TaskEditForm', () => ({
  TaskEditForm: ({ editTitle }: { editTitle: string }) => (
    <div data-testid="edit-tab">
      <input defaultValue={editTitle} />
    </div>
  ),
}))

vi.mock('../../components/AiRunsTab', () => ({
  AiRunsTab: () => <div data-testid="ai-runs-tab">AI Runs</div>,
}))

vi.mock('../../auth', () => ({
  useAuth: vi.fn(() => ({ token: 'test-token' })),
}))

vi.mock('../../api', () => ({
  api: {
    listTasks: vi.fn(),
    listComments: vi.fn(),
    addComment: vi.fn(),
    updateTask: vi.fn(),
    deleteTask: vi.fn(),
  },
}))

import React from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import type { Task, Member } from '../../api'
import { TaskDetail } from '../TaskDetail'

const MEMBERS: Member[] = [
  { user_id: 'u1', username: 'alice', role: 'member', added_at: '2026-01-01' },
]

const MOCK_TASK: Task = {
  id: 'task-1', project_id: 'proj-1',
  title: 'Design primer sequences',
  description: 'Use BLAST to verify specificity',
  assignee_id: null, status: 'todo', priority: 'high',
  deadline: '2099-12-31', session_id: null,
  created_by: 'u1', created_at: '2026-01-01', updated_at: '2026-01-01',
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useQuery).mockReturnValue({ data: [] } as any)
  vi.mocked(useMutation).mockReturnValue({ mutate: mockMutate, isPending: false } as any)
})

describe('TaskDetail', () => {
  test('renders all four tabs', () => {
    render(<TaskDetail task={MOCK_TASK} projectId="p1" onClose={vi.fn()} members={MEMBERS} />)
    expect(screen.getByRole('button', { name: /^DETAILS$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^NOTES$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /AI RUNS/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^EDIT$/i })).toBeInTheDocument()
  })

  test('shows DETAILS tab by default', () => {
    render(<TaskDetail task={MOCK_TASK} projectId="p1" onClose={vi.fn()} members={MEMBERS} />)
    expect(screen.getByTestId('details-tab')).toBeInTheDocument()
    expect(screen.queryByTestId('notes-tab')).toBeNull()
  })

  test('switches to NOTES tab', () => {
    render(<TaskDetail task={MOCK_TASK} projectId="p1" onClose={vi.fn()} members={MEMBERS} />)
    fireEvent.click(screen.getByRole('button', { name: /^NOTES$/i }))
    expect(screen.getByTestId('notes-tab')).toBeInTheDocument()
    expect(screen.queryByTestId('details-tab')).toBeNull()
  })

  test('switches to AI RUNS tab', () => {
    render(<TaskDetail task={MOCK_TASK} projectId="p1" onClose={vi.fn()} members={MEMBERS} />)
    fireEvent.click(screen.getByRole('button', { name: /AI RUNS/i }))
    expect(screen.getByTestId('ai-runs-tab')).toBeInTheDocument()
  })

  test('switches to EDIT tab', () => {
    render(<TaskDetail task={MOCK_TASK} projectId="p1" onClose={vi.fn()} members={MEMBERS} />)
    fireEvent.click(screen.getByRole('button', { name: /^EDIT$/i }))
    expect(screen.getByTestId('edit-tab')).toBeInTheDocument()
  })

  test('close button calls onClose', () => {
    const onClose = vi.fn()
    render(<TaskDetail task={MOCK_TASK} projectId="p1" onClose={onClose} members={MEMBERS} />)
    fireEvent.click(screen.getByRole('button', { name: /✕/i }))
    expect(onClose).toHaveBeenCalled()
  })

  test('clicking overlay calls onClose', () => {
    const onClose = vi.fn()
    const { container } = render(
      <TaskDetail task={MOCK_TASK} projectId="p1" onClose={onClose} members={MEMBERS} />
    )
    fireEvent.click(container.firstChild as Element)
    expect(onClose).toHaveBeenCalled()
  })
})
