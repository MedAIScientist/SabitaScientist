import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi, beforeEach } from 'vitest'
import { Task } from '../../api'

// Mock TanStack Query
const mockMutate = vi.fn()
const mockInvalidateQueries = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useMutation: vi.fn(),
  useQueryClient: vi.fn(() => ({ invalidateQueries: mockInvalidateQueries })),
}))

import { useMutation } from '@tanstack/react-query'
import { CardEditPopover } from '../CardEditPopover'

const MOCK_TASK: Task = {
  id: 'task-1',
  project_id: 'proj-1',
  title: 'Sequence CRISPR samples',
  description: null,
  assignee_id: null,
  status: 'in_progress',
  priority: 'medium',
  deadline: '2026-06-15',
  session_id: null,
  created_by: 'user-1',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const MOCK_ANCHOR_RECT = {
  top: 100,
  left: 200,
  right: 400,
  bottom: 140,
  width: 200,
  height: 40,
  x: 200,
  y: 100,
  toJSON: () => ({}),
} as DOMRect

function renderPopover(isPending: boolean, onClose = vi.fn()) {
  const mockedUseMutation = vi.mocked(useMutation)
  mockedUseMutation.mockReturnValue({
    mutate: mockMutate,
    isPending,
  } as any)

  return render(
    <CardEditPopover
      task={MOCK_TASK}
      projectId="proj-1"
      anchorRect={MOCK_ANCHOR_RECT}
      onClose={onClose}
    />
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('CardEditPopover', () => {
  test('renders title input with task title as initial value', () => {
    renderPopover(false)
    const input = screen.getByDisplayValue('Sequence CRISPR samples')
    expect(input).toBeInTheDocument()
  })

  test('renders priority select with task priority pre-selected', () => {
    renderPopover(false)
    const select = screen.getByRole('combobox') as HTMLSelectElement
    expect(select.value).toBe('medium')
  })

  test('renders CRITICAL/STANDARD/ROUTINE options in priority select', () => {
    renderPopover(false)
    expect(screen.getByRole('option', { name: 'CRITICAL' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'STANDARD' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'ROUTINE' })).toBeInTheDocument()
  })

  test('calls onClose when Escape key pressed', () => {
    const onClose = vi.fn()
    renderPopover(false, onClose)
    const panel = screen.getByRole('dialog')
    fireEvent.keyDown(panel, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  test('calls onClose when clicking outside the panel', () => {
    const onClose = vi.fn()
    renderPopover(false, onClose)
    fireEvent.mouseDown(document.body)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  test('save button is disabled and shows "saving…" when mutation isPending=true', () => {
    renderPopover(true)
    const btn = screen.getByRole('button', { name: /saving/i })
    expect(btn).toBeDisabled()
  })
})
