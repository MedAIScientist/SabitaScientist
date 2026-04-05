import { render, screen, fireEvent, act } from '@testing-library/react'
import { describe, test, expect, vi, beforeEach } from 'vitest'

// ── TanStack Query mocks ──────────────────────────────────────────────────────
const mockInvalidateQueries = vi.fn()
const mockMutate = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
  useQueryClient: vi.fn(() => ({ invalidateQueries: mockInvalidateQueries })),
}))

// ── API mock ──────────────────────────────────────────────────────────────────
vi.mock('../../api', () => ({
  api: {
    listComments: vi.fn(),
    addComment: vi.fn(),
    updateTask: vi.fn(),
    deleteTask: vi.fn(),
  },
}))

import React from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Task, Member } from '../../api'
import { TaskDetail } from '../TaskDetail'

// ── Sample data ───────────────────────────────────────────────────────────────
const MEMBERS: Member[] = [
  { user_id: 'u1', username: 'alice', role: 'member', added_at: '2026-01-01' },
  { user_id: 'u2', username: 'bob', role: 'admin', added_at: '2026-01-01' },
]

const FUTURE_DATE = '2099-12-31'
const PAST_DATE = '2020-01-01'

const MOCK_TASK: Task = {
  id: 'task-1',
  project_id: 'proj-1',
  title: 'Design primer sequences',
  description: 'Use BLAST to verify specificity',
  assignee_id: null,
  status: 'todo',
  priority: 'high',
  deadline: FUTURE_DATE,
  session_id: null,
  created_by: 'u1',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const OVERDUE_TASK: Task = {
  ...MOCK_TASK,
  id: 'task-overdue',
  title: 'Submit sequencing order',
  deadline: PAST_DATE,
  status: 'in_progress',
  priority: 'medium',
}

const onClose = vi.fn()

function renderDetail(task: Task = MOCK_TASK) {
  return render(
    <TaskDetail
      task={task}
      projectId="proj-1"
      onClose={onClose}
      members={MEMBERS}
    />
  )
}

// ── Setup mocks before each test ──────────────────────────────────────────────
beforeEach(() => {
  vi.clearAllMocks()

  vi.mocked(useQuery).mockReturnValue({ data: [] } as any)

  vi.mocked(useMutation).mockReturnValue({
    mutate: mockMutate,
    isPending: false,
  } as any)
})

// ── Tests ─────────────────────────────────────────────────────────────────────
describe('TaskDetail', () => {
  test('renders task title in view mode', () => {
    renderDetail()
    expect(screen.getByText('Design primer sequences')).toBeInTheDocument()
  })

  test('renders EDIT button in header', () => {
    renderDetail()
    expect(screen.getByRole('button', { name: /EDIT/i })).toBeInTheDocument()
  })

  test('clicking EDIT shows title input with current value', () => {
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /EDIT/i }))
    const titleInput = screen.getByDisplayValue('Design primer sequences')
    expect(titleInput).toBeInTheDocument()
    expect(titleInput.tagName).toBe('INPUT')
  })

  test('clicking CANCEL in edit mode returns to view mode', () => {
    renderDetail()
    // Enter edit mode
    fireEvent.click(screen.getByRole('button', { name: /EDIT/i }))
    expect(screen.getByDisplayValue('Design primer sequences')).toBeInTheDocument()

    // Click CANCEL
    fireEvent.click(screen.getByRole('button', { name: /CANCEL/i }))

    // Should be back to view mode (input gone, title text visible)
    expect(screen.queryByDisplayValue('Design primer sequences')).toBeNull()
    expect(screen.getByText('Design primer sequences')).toBeInTheDocument()
  })

  test('renders status select with correct options (PLANNED/IN PROGRESS/COMPLETE) in edit mode', () => {
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /EDIT/i }))

    const options = screen.getAllByRole('option')
    const optionTexts = options.map(o => o.textContent)
    expect(optionTexts).toContain('PLANNED')
    expect(optionTexts).toContain('IN PROGRESS')
    expect(optionTexts).toContain('COMPLETE')
  })

  test('renders DELETE button in edit mode', () => {
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /EDIT/i }))
    expect(screen.getByRole('button', { name: /DELETE/i })).toBeInTheDocument()
  })

  test('clicking DELETE once changes button to "CONFIRM DELETE ?"', () => {
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /EDIT/i }))
    const deleteBtn = screen.getByRole('button', { name: /^DELETE$/i })
    fireEvent.click(deleteBtn)
    expect(screen.getByRole('button', { name: /CONFIRM DELETE/i })).toBeInTheDocument()
  })

  test('overdue task shows deadline badge with rose color', () => {
    renderDetail(OVERDUE_TASK)
    // Find the deadline badge — it should display the past date
    const badges = screen.getAllByText((content) => content.includes(PAST_DATE))
    // The deadline badge element should have rose-colored styling
    const deadlineBadge = badges.find(el =>
      el.tagName === 'SPAN' && el.textContent?.includes(PAST_DATE)
    )
    expect(deadlineBadge).not.toBeUndefined()
    // Check for rose color styling (#f43f5e → rgb(244, 63, 94) after jsdom normalization)
    const style = deadlineBadge!.getAttribute('style') ?? ''
    expect(style).toMatch(/f43f5e|rgb\(244,\s*63,\s*94\)/i)
  })
})
