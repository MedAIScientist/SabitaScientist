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
  // Each render cycle calls useQuery 4 times: project, tasks, experiments, phases.
  // Provide enough mock returns to cover initial render + re-renders triggered by state updates.
  const projectReturn = { data: MOCK_PROJECT } as any
  const tasksReturn   = { data: TASKS }        as any
  const expsReturn    = { data: [] }            as any
  const phasesReturn  = { data: [] }            as any
  mockedUseQuery
    .mockReturnValueOnce(projectReturn)
    .mockReturnValueOnce(tasksReturn)
    .mockReturnValueOnce(expsReturn)
    .mockReturnValueOnce(phasesReturn)
    // extra cycles for tests that trigger re-renders (e.g. bulk selection)
    .mockReturnValueOnce(projectReturn)
    .mockReturnValueOnce(tasksReturn)
    .mockReturnValueOnce(expsReturn)
    .mockReturnValueOnce(phasesReturn)
    .mockReturnValueOnce(projectReturn)
    .mockReturnValueOnce(tasksReturn)
    .mockReturnValueOnce(expsReturn)
    .mockReturnValueOnce(phasesReturn)

  vi.mocked(useMutation).mockReturnValue({
    mutate: mockMutate,
    isPending: false,
  } as any)
})

// ── Tests ─────────────────────────────────────────────────────────────────────
describe('Board', () => {
  test('renders three lab column headers: PLANNED, IN PROGRESS, COMPLETE', () => {
    renderBoard()
    expect(screen.getByText(/^PLANNED$/i)).toBeInTheDocument()
    expect(screen.getByText(/^IN PROGRESS$/i)).toBeInTheDocument()
    expect(screen.getByText(/^COMPLETE$/i)).toBeInTheDocument()
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
    expect(screen.getByText(/Settings/i)).toBeInTheDocument()
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
    expect(screen.queryByText(/Settings/i)).not.toBeInTheDocument()
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

  test('selecting a card renders BulkActionBar with count 1', () => {
    renderBoard()
    const cardTitle = screen.getByText('Design primer sequences')
    const card = cardTitle.closest('[data-card="true"]') as HTMLElement
    expect(card).not.toBeNull()
    fireEvent.mouseEnter(card)
    const checkbox = card.querySelector('input[type="checkbox"]') as HTMLElement
    expect(checkbox).not.toBeNull()
    fireEvent.click(checkbox)
    expect(screen.getByText(/1 task selected/i)).toBeInTheDocument()
  })

  test('clearing selection hides BulkActionBar', () => {
    renderBoard()
    const cardTitle = screen.getByText('Design primer sequences')
    const card = cardTitle.closest('[data-card="true"]') as HTMLElement
    fireEvent.mouseEnter(card)
    const checkbox = card.querySelector('input[type="checkbox"]') as HTMLElement
    fireEvent.click(checkbox)
    expect(screen.getByText(/1 task selected/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /clear/i }))
    expect(screen.queryByText(/1 task selected/i)).toBeNull()
  })
})

// ── Adding a task belongs to the cell that was clicked ────────────────────────
//
// Reported: "+ Add task" opened in every phase at once, and the task then appeared
// under "Unassigned" instead of the phase whose column was clicked.

describe('Board — adding a task to a specific phase column', () => {
  const LANE_A: ProjectPhase = {
    id: 'phase-a', project_id: 'proj-1', name: 'Data Analysis', color: '#8b5cf6',
    position: 0, target_date: null, created_by: 'u1', created_at: '2026-01-01',
  }
  const LANE_B: ProjectPhase = {
    id: 'phase-b', project_id: 'proj-1', name: 'Writing', color: '#10b981',
    position: 1, target_date: null, created_by: 'u1', created_at: '2026-01-01',
  }

  function renderWithPhases() {
    vi.mocked(useQuery).mockReset()
    const projectReturn = { data: MOCK_PROJECT } as any
    const tasksReturn = { data: TASKS } as any
    const expsReturn = { data: [] } as any
    const phasesReturn = { data: [LANE_A, LANE_B] } as any
    for (let cycle = 0; cycle < 4; cycle++) {
      vi.mocked(useQuery)
        .mockReturnValueOnce(projectReturn)
        .mockReturnValueOnce(tasksReturn)
        .mockReturnValueOnce(expsReturn)
        .mockReturnValueOnce(phasesReturn)
    }
    renderBoard()
  }

  /** The "+ Add task" button belonging to one phase's PLANNED column. */
  function addButtonFor(phaseName: string): HTMLElement {
    const lane = screen.getByText(phaseName).closest('div')!.parentElement!
    const buttons = Array.from(lane.querySelectorAll('button')).filter(b => /Add task/i.test(b.textContent || ''))
    expect(buttons.length).toBeGreaterThan(0)
    return buttons[0]
  }

  test('opens the form in one column only, not in every phase', () => {
    renderWithPhases()
    expect(screen.queryAllByPlaceholderText('Task title…')).toHaveLength(0)

    fireEvent.click(addButtonFor('Data Analysis'))

    // Before the fix this was 3 per phase: the form was keyed on the status alone.
    expect(screen.getAllByPlaceholderText('Task title…')).toHaveLength(1)
  })

  test('sends the clicked phase with the new task', () => {
    renderWithPhases()
    fireEvent.click(addButtonFor('Writing'))

    const input = screen.getByPlaceholderText('Task title…')
    fireEvent.change(input, { target: { value: 'Draft the methods' } })
    fireEvent.submit(input.closest('form')!)

    expect(mockMutate).toHaveBeenCalledWith({
      title: 'Draft the methods',
      status: 'todo',
      phaseId: 'phase-b',
    })
  })

  test('the mutation creates the task in that phase', async () => {
    renderWithPhases()
    // The first useMutation in Board is the create-task one.
    const createConfig = vi.mocked(useMutation).mock.calls[0][0] as { mutationFn: (v: unknown) => Promise<unknown> }
    await createConfig.mutationFn({ title: 'Draft the methods', status: 'todo', phaseId: 'phase-b' })

    const { api } = await import('../../api')
    expect(vi.mocked(api.createTask)).toHaveBeenCalledWith('proj-1', {
      title: 'Draft the methods',
      status: 'todo',
      phase_id: 'phase-b',
    })
  })

  test('the unassigned lane creates a task with no phase', () => {
    renderWithPhases()
    fireEvent.click(addButtonFor('Unassigned'))

    const input = screen.getByPlaceholderText('Task title…')
    fireEvent.change(input, { target: { value: 'Loose end' } })
    fireEvent.submit(input.closest('form')!)

    expect(mockMutate).toHaveBeenCalledWith({
      title: 'Loose end',
      status: 'todo',
      phaseId: null,
    })
  })
})
