// EvoScientist/pm/frontend/src/components/__tests__/TaskEditForm.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi } from 'vitest'
import { TaskEditForm } from '../task/TaskEditForm'
import type { Task, Member } from '../../api'

// Mock DeadlinePicker — it uses date logic we don't need to test here
vi.mock('../DeadlinePicker', () => ({
  DeadlinePicker: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <input
      data-testid="deadline-picker"
      value={value}
      onChange={e => onChange(e.target.value)}
    />
  ),
}))

const MEMBERS: Member[] = [
  { user_id: 'u1', username: 'alice', role: 'member', added_at: '2026-01-01' },
  { user_id: 'u2', username: 'bob',   role: 'admin',  added_at: '2026-01-01' },
]

const DEFAULT_PROPS = {
  editTitle: 'Design primer sequences',
  setEditTitle: vi.fn(),
  editStatus: 'todo' as Task['status'],
  setEditStatus: vi.fn(),
  editPriority: 'high' as Task['priority'],
  setEditPriority: vi.fn(),
  editDeadline: '2099-12-31',
  setEditDeadline: vi.fn(),
  editDescription: 'Use BLAST to verify',
  setEditDescription: vi.fn(),
  editAssigneeId: '',
  setEditAssigneeId: vi.fn(),
  onSave: vi.fn(),
  onDeleteClick: vi.fn(),
  isSaving: false,
  isDeleting: false,
  deleteConfirm: false,
  members: MEMBERS,
}

describe('TaskEditForm', () => {
  test('renders title input with current value', () => {
    render(<TaskEditForm {...DEFAULT_PROPS} />)
    expect(screen.getByDisplayValue('Design primer sequences')).toBeInTheDocument()
  })

  test('renders status select with PLANNED/IN PROGRESS/COMPLETE options', () => {
    render(<TaskEditForm {...DEFAULT_PROPS} />)
    const options = screen.getAllByRole('option').map(o => o.textContent)
    expect(options).toContain('PLANNED')
    expect(options).toContain('IN PROGRESS')
    expect(options).toContain('COMPLETE')
  })

  test('renders priority select with CRITICAL/STANDARD/ROUTINE options', () => {
    render(<TaskEditForm {...DEFAULT_PROPS} />)
    const options = screen.getAllByRole('option').map(o => o.textContent)
    expect(options).toContain('CRITICAL')
    expect(options).toContain('STANDARD')
    expect(options).toContain('ROUTINE')
  })

  test('renders member options in assignee select', () => {
    render(<TaskEditForm {...DEFAULT_PROPS} />)
    expect(screen.getByRole('option', { name: 'alice' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'bob' })).toBeInTheDocument()
  })

  test('SAVE button disabled while isSaving', () => {
    render(<TaskEditForm {...DEFAULT_PROPS} isSaving={true} />)
    expect(screen.getByRole('button', { name: /saving/i })).toBeDisabled()
  })

  test('SAVE button calls onSave when clicked', () => {
    const onSave = vi.fn()
    render(<TaskEditForm {...DEFAULT_PROPS} onSave={onSave} />)
    fireEvent.click(screen.getByRole('button', { name: /^SAVE$/i }))
    expect(onSave).toHaveBeenCalled()
  })

  test('shows DELETE button text when deleteConfirm is false', () => {
    render(<TaskEditForm {...DEFAULT_PROPS} deleteConfirm={false} />)
    expect(screen.getByRole('button', { name: /^DELETE$/i })).toBeInTheDocument()
  })

  test('shows CONFIRM DELETE text when deleteConfirm is true', () => {
    render(<TaskEditForm {...DEFAULT_PROPS} deleteConfirm={true} />)
    expect(screen.getByRole('button', { name: /CONFIRM DELETE/i })).toBeInTheDocument()
  })

  test('clicking DELETE calls onDeleteClick', () => {
    const onDeleteClick = vi.fn()
    render(<TaskEditForm {...DEFAULT_PROPS} onDeleteClick={onDeleteClick} />)
    fireEvent.click(screen.getByRole('button', { name: /^DELETE$/i }))
    expect(onDeleteClick).toHaveBeenCalled()
  })
})
