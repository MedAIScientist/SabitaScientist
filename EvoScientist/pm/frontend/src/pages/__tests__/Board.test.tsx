import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi, beforeEach, it } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

// ── DnD-kit mocks (jsdom-safe) ────────────────────────────────────────────────
vi.mock('@dnd-kit/core', () => ({
  DndContext: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  PointerSensor: class {},
  useSensor: () => ({}),
  useSensors: (...args: unknown[]) => args,
  useDraggable: () => ({ attributes: {}, listeners: {}, setNodeRef: () => {}, transform: null }),
  useDroppable: () => ({ setNodeRef: () => {}, isOver: false }),
}))
vi.mock('@dnd-kit/utilities', () => ({
  CSS: { Transform: { toString: () => '' } },
}))

// ── TanStack Query mocks ──────────────────────────────────────────────────────
const mockInvalidateQueries = vi.fn()
const mockMutate = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
  useQueryClient: vi.fn(() => ({ invalidateQueries: mockInvalidateQueries })),
}))

// ── Auth mock ─────────────────────────────────────────────────────────────────
vi.mock('../../auth', () => ({
  useAuth: vi.fn(() => ({ username: 'alice', token: 'test-token' })),
}))

// ── ProjectSettingsPanel mock ─────────────────────────────────────────────────
vi.mock('../../components/ProjectSettingsPanel', () => ({
  ProjectSettingsPanel: () => <div data-testid="settings-panel" />,
}))

// ── API mock ──────────────────────────────────────────────────────────────────
vi.mock('../../api', () => ({
  api: {
    getProject: vi.fn(),
    listTasks: vi.fn(),
    createTask: vi.fn(),
    updateTask: vi.fn(),
  },
  listPhases: vi.fn(),
}))

import React from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useAuth } from '../../auth'
import { Task, Member, Project, ProjectPhase } from '../../api'
import { Board } from '../Board'

// ── Sample data ───────────────────────────────────────────────────────────────
const MEMBERS: Member[] = [
  { user_id: 'u1', username: 'alice', role: 'viewer', added_at: '2026-01-01' },
]

const MOCK_PROJECT: Project = {
  id: 'proj-1',
  name: 'CRISPR Study',
  description: null,
  created_by: 'u1',
  created_at: '2026-01-01T00:00:00Z',
  archived_at: null,
  members: MEMBERS,
}

const FUTURE_DATE = '2099-12-31'
const PAST_DATE   = '2020-01-01'

const TASKS: Task[] = [
  {
    id: 'task-1', project_id: 'proj-1', title: 'Design primer sequences',
    description: null, assignee_id: null, status: 'todo',
    priority: 'high', deadline: FUTURE_DATE,
    session_id: null, created_by: 'u1',
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'task-2', project_id: 'proj-1', title: 'Run gel electrophoresis',
    description: null, assignee_id: null, status: 'in_progress',
    priority: 'medium', deadline: null,
    session_id: null, created_by: 'u1',
    created_at: '2026-01-02T00:00:00Z', updated_at: '2026-01-02T00:00:00Z',
  },
  {
    id: 'task-overdue', project_id: 'proj-1', title: 'Submit sequencing order',
    description: null, assignee_id: null, status: 'in_progress',
    priority: 'high', deadline: PAST_DATE,
    session_id: null, created_by: 'u1',
    created_at: '2026-01-03T00:00:00Z', updated_at: '2026-01-03T00:00:00Z',
  },
]

// ── Helper to render Board under MemoryRouter ─────────────────────────────────
function renderBoard() {
  return render(
    <MemoryRouter initialEntries={['/board/proj-1']}>
      <Routes>
        <Route path="/board/:id" element={<Board />} />
      </Routes>
    </MemoryRouter>
  )
}

// ── Setup mocks before each test ──────────────────────────────────────────────
beforeEach(() => {
  vi.clearAllMocks()

  const mockedUseQuery = vi.mocked(useQuery)
  // First call → project, second call → tasks, third call → experiments, fourth call → phases
  mockedUseQuery
    .mockReturnValueOnce({ data: MOCK_PROJECT } as any)
    .mockReturnValueOnce({ data: TASKS } as any)
    .mockReturnValueOnce({ data: [] } as any)
    .mockReturnValueOnce({ data: [] } as any)

  vi.mocked(useMutation).mockReturnValue({
    mutate: mockMutate,
    isPending: false,
  } as any)
})

// ── Tests ─────────────────────────────────────────────────────────────────────
describe('Board', () => {
  test('renders three lab column headers: PLANNED, IN PROGRESS, COMPLETE', () => {
    renderBoard()
    expect(screen.getByText('PLANNED')).toBeInTheDocument()
    expect(screen.getByText('IN PROGRESS')).toBeInTheDocument()
    expect(screen.getByText('COMPLETE')).toBeInTheDocument()
  })

  test('renders FilterToolbar (search input with 🔬 placeholder present)', () => {
    renderBoard()
    const input = screen.getByPlaceholderText('🔬 Search experiments…')
    expect(input).toBeInTheDocument()
  })

  test('task card with status todo appears under PLANNED column', () => {
    renderBoard()
    // The task title should be in the DOM
    expect(screen.getByText('Design primer sequences')).toBeInTheDocument()
  })

  test('overdue task card has rose left border style', () => {
    renderBoard()
    // "Submit sequencing order" has a past deadline → overdue
    const cardTitle = screen.getByText('Submit sequencing order')
    const card = cardTitle.closest('[data-card="true"]') as HTMLElement
    expect(card).not.toBeNull()
    // jsdom normalizes hex to rgb, so check for the rgb equivalent of #f43f5e
    expect(card.style.borderLeft).toMatch(/3px solid (rgb\(244, 63, 94\)|#f43f5e)/)
  })

  test('non-overdue task does NOT have rose border', () => {
    renderBoard()
    // "Design primer sequences" has a future deadline → not overdue
    const cardTitle = screen.getByText('Design primer sequences')
    const card = cardTitle.closest('[data-card="true"]') as HTMLElement
    expect(card).not.toBeNull()
    // Should not have the rose (#f43f5e / rgb(244,63,94)) left border
    expect(card.style.borderLeft).not.toMatch(/3px solid (rgb\(244, 63, 94\)|#f43f5e)/)
  })

  test('edit pencil button (✎) appears when card is hovered', () => {
    renderBoard()
    const cardTitle = screen.getByText('Design primer sequences')
    const card = cardTitle.closest('[data-card="true"]') as HTMLElement
    expect(card).not.toBeNull()

    // Before hover: no edit button visible
    expect(screen.queryByTitle('Edit')).toBeNull()

    // Simulate hover on the card
    fireEvent.mouseEnter(card)

    // After hover: edit button should appear
    const editBtn = card.querySelector('button[title="Edit"]')
    expect(editBtn).not.toBeNull()
  })

  test('⚙ SETTINGS button is visible for project owner', () => {
    const ownerMembers: Member[] = [
      { user_id: 'u1', username: 'owner_user', role: 'owner', added_at: '2026-01-01' },
    ]
    const ownerProject: Project = { ...MOCK_PROJECT, members: ownerMembers }

    vi.mocked(useAuth).mockReturnValue({ username: 'owner_user', token: 'test-token' } as any)
    vi.mocked(useQuery).mockReset()
    vi.mocked(useQuery)
      .mockReturnValueOnce({ data: ownerProject } as any)
      .mockReturnValueOnce({ data: TASKS } as any)
      .mockReturnValueOnce({ data: [] } as any)
      .mockReturnValueOnce({ data: [] } as any)

    renderBoard()
    expect(screen.getByText(/⚙ SETTINGS/i)).toBeInTheDocument()
  })

  test('⚙ SETTINGS button is hidden for non-owner members', () => {
    const viewerMembers: Member[] = [
      { user_id: 'u2', username: 'viewer_user', role: 'viewer', added_at: '2026-01-01' },
    ]
    const viewerProject: Project = { ...MOCK_PROJECT, members: viewerMembers }

    vi.mocked(useAuth).mockReturnValue({ username: 'viewer_user', token: 'test-token' } as any)
    vi.mocked(useQuery).mockReset()
    vi.mocked(useQuery)
      .mockReturnValueOnce({ data: viewerProject } as any)
      .mockReturnValueOnce({ data: TASKS } as any)
      .mockReturnValueOnce({ data: [] } as any)
      .mockReturnValueOnce({ data: [] } as any)

    renderBoard()
    expect(screen.queryByText(/⚙ SETTINGS/i)).not.toBeInTheDocument()
  })

  it('renders swimlanes when phases exist', () => {
    const PHASE: ProjectPhase = {
      id: 'p1',
      project_id: 'proj1',
      name: 'Sprint 1',
      color: '#6366f1',
      position: 0,
      target_date: null,
      created_by: 'u1',
      created_at: '2024-01-01',
    }

    vi.mocked(useQuery).mockReset()
    vi.mocked(useQuery)
      .mockReturnValueOnce({ data: MOCK_PROJECT } as any)
      .mockReturnValueOnce({ data: TASKS } as any)
      .mockReturnValueOnce({ data: [] } as any)
      .mockReturnValueOnce({ data: [PHASE] } as any)

    renderBoard()
    expect(screen.getByText('Sprint 1')).toBeInTheDocument()
  })
})
