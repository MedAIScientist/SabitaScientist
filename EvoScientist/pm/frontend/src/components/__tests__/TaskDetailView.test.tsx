// EvoScientist/pm/frontend/src/components/__tests__/TaskDetailView.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi } from 'vitest'
import { TaskDetailView } from '../task/TaskDetailView'
import type { Task, Member } from '../../api'

// Mock DependencyPicker — it owns its own queries
vi.mock('../DependencyPicker', () => ({
  DependencyPicker: () => <div data-testid="dependency-picker" />,
}))

const MEMBERS: Member[] = [
  { user_id: 'u1', username: 'alice', role: 'member', added_at: '2026-01-01' },
]

const BASE_TASK: Task = {
  id: 'task-1', project_id: 'proj-1',
  title: 'Design primer sequences',
  description: 'Use BLAST to verify specificity',
  assignee_id: 'u1', status: 'todo', priority: 'high',
  deadline: '2099-12-31', session_id: null,
  created_by: 'u1', created_at: '2026-01-01', updated_at: '2026-01-01',
}

describe('TaskDetailView', () => {
  test('renders status badge label', () => {
    render(
      <TaskDetailView
        task={BASE_TASK} projectId="p1" members={MEMBERS}
        token="tok" allTasks={[]} copied={false} onCopySessionId={vi.fn()}
      />
    )
    expect(screen.getByText('PLANNED')).toBeInTheDocument()
  })

  test('renders priority badge label', () => {
    render(
      <TaskDetailView
        task={BASE_TASK} projectId="p1" members={MEMBERS}
        token="tok" allTasks={[]} copied={false} onCopySessionId={vi.fn()}
      />
    )
    expect(screen.getByText('CRITICAL')).toBeInTheDocument()
  })

  test('renders BLOCKED badge when blocked_by is non-empty', () => {
    const blockedTask = { ...BASE_TASK, blocked_by: ['other-task-id'] }
    render(
      <TaskDetailView
        task={blockedTask as Task} projectId="p1" members={MEMBERS}
        token="tok" allTasks={[]} copied={false} onCopySessionId={vi.fn()}
      />
    )
    expect(screen.getByText('BLOCKED')).toBeInTheDocument()
  })

  test('does not render BLOCKED badge when blocked_by is empty', () => {
    const freeTask = { ...BASE_TASK, blocked_by: [] }
    render(
      <TaskDetailView
        task={freeTask as Task} projectId="p1" members={MEMBERS}
        token="tok" allTasks={[]} copied={false} onCopySessionId={vi.fn()}
      />
    )
    expect(screen.queryByText('BLOCKED')).toBeNull()
  })

  test('renders assignee username', () => {
    render(
      <TaskDetailView
        task={BASE_TASK} projectId="p1" members={MEMBERS}
        token="tok" allTasks={[]} copied={false} onCopySessionId={vi.fn()}
      />
    )
    expect(screen.getByText('alice')).toBeInTheDocument()
  })

  test('renders session card when session_id is set', () => {
    const taskWithSession = { ...BASE_TASK, session_id: 'sess-abc123' }
    render(
      <TaskDetailView
        task={taskWithSession} projectId="p1" members={MEMBERS}
        token="tok" allTasks={[]} copied={false} onCopySessionId={vi.fn()}
      />
    )
    expect(screen.getByText('sess-abc123')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument()
  })

  test('copy button shows checkmark when copied=true', () => {
    const taskWithSession = { ...BASE_TASK, session_id: 'sess-abc123' }
    render(
      <TaskDetailView
        task={taskWithSession} projectId="p1" members={MEMBERS}
        token="tok" allTasks={[]} copied={true} onCopySessionId={vi.fn()}
      />
    )
    expect(screen.getByText(/copied/i)).toBeInTheDocument()
  })

  test('copy button calls onCopySessionId when clicked', () => {
    const onCopy = vi.fn()
    const taskWithSession = { ...BASE_TASK, session_id: 'sess-abc123' }
    render(
      <TaskDetailView
        task={taskWithSession} projectId="p1" members={MEMBERS}
        token="tok" allTasks={[]} copied={false} onCopySessionId={onCopy}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /copy/i }))
    expect(onCopy).toHaveBeenCalled()
  })

  test('renders DependencyPicker when token provided', () => {
    render(
      <TaskDetailView
        task={BASE_TASK} projectId="p1" members={MEMBERS}
        token="tok" allTasks={[]} copied={false} onCopySessionId={vi.fn()}
      />
    )
    expect(screen.getByTestId('dependency-picker')).toBeInTheDocument()
  })

  test('does not render DependencyPicker when token is null', () => {
    render(
      <TaskDetailView
        task={BASE_TASK} projectId="p1" members={MEMBERS}
        token={null} allTasks={[]} copied={false} onCopySessionId={vi.fn()}
      />
    )
    expect(screen.queryByTestId('dependency-picker')).toBeNull()
  })
})
