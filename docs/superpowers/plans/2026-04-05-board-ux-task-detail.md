# Board UX & Task Detail — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add drag-and-drop between kanban columns, a filter toolbar, a card quick-edit popover, full task editing in the drawer (with assignee + delete), and overdue highlighting — all framed for biology lab scientists tracking experiments and protocols.

**Architecture:** Pure frontend changes — no new API endpoints needed. All mutations use the existing `api.updateTask` (PUT) and `api.deleteTask` (DELETE) functions in `api.ts`. Client-side filtering with `useMemo`. Drag-and-drop via `@dnd-kit/core` (cross-column only, no within-column reordering). Lab-appropriate display labels throughout (`CRITICAL/STANDARD/ROUTINE`, `PLANNED/ACTIVE/COMPLETE`).

**Tech Stack:** React 18, Vite, TypeScript, `@dnd-kit/core` + `@dnd-kit/sortable` + `@dnd-kit/utilities`, TanStack Query v5, vitest + @testing-library/react, inline styles + CSS custom properties (`--font-mono`, `--font-sans`, `--bg`, `--surface`, `--border`).

**Codebase context:**
- Frontend root: `EvoScientist/pm/frontend/`
- Pages: `src/pages/Board.tsx`, `src/pages/TaskDetail.tsx`
- API layer: `src/api.ts` — `api.updateTask(projectId, taskId, data)` uses PUT; `api.deleteTask(projectId, taskId)` uses DELETE
- `Task` interface has: `id`, `title`, `status: 'todo'|'in_progress'|'done'`, `priority: 'high'|'medium'|'low'`, `deadline: string|null`, `assignee_id: string|null`, `description: string|null`, `created_at`, `updated_at`
- `Member` interface: `user_id`, `username`, `role`, `added_at`
- Tests run with: `cd EvoScientist/pm/frontend && npm test`
- Build: `cd EvoScientist/pm/frontend && npm run build`

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `src/hooks/useTaskFilters.ts` | Create | Filter/sort logic for the board |
| `src/hooks/__tests__/useTaskFilters.test.ts` | Create | Tests for filter hook |
| `src/components/FilterToolbar.tsx` | Create | Search + priority chips + sort + assignee row |
| `src/components/__tests__/FilterToolbar.test.tsx` | Create | Tests for FilterToolbar |
| `src/components/CardEditPopover.tsx` | Create | Floating quick-edit panel for a task card |
| `src/components/__tests__/CardEditPopover.test.tsx` | Create | Tests for CardEditPopover |
| `src/pages/Board.tsx` | Modify | Add DnD, FilterToolbar, hover icon, overdue border |
| `src/pages/TaskDetail.tsx` | Modify | Add edit mode, assignee, delete, overdue badge |
| `package.json` | Modify | Add @dnd-kit dependencies |

---

## Task 1: Install @dnd-kit packages

**Files:**
- Modify: `EvoScientist/pm/frontend/package.json`

- [ ] **Step 1: Install the packages**

```bash
cd EvoScientist/pm/frontend
npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
```

Expected output: `added N packages` — no errors. `node_modules/@dnd-kit/` directory now exists.

- [ ] **Step 2: Verify build still works**

```bash
npm run build
```

Expected: `✓ built in ...ms` — no TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add EvoScientist/pm/frontend/package.json EvoScientist/pm/frontend/package-lock.json
git commit -m "chore(pm): add @dnd-kit/core, sortable, utilities"
```

---

## Task 2: Create `useTaskFilters` hook

**Files:**
- Create: `EvoScientist/pm/frontend/src/hooks/useTaskFilters.ts`
- Create: `EvoScientist/pm/frontend/src/hooks/__tests__/useTaskFilters.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `EvoScientist/pm/frontend/src/hooks/__tests__/useTaskFilters.test.ts`:

```typescript
import { renderHook, act } from '@testing-library/react'
import { describe, test, expect } from 'vitest'
import { useTaskFilters } from '../useTaskFilters'
import { Task } from '../../api'

const TASKS: Task[] = [
  {
    id: '1', project_id: 'p1', title: 'Baseline PCR run',
    priority: 'high', status: 'todo', deadline: '2026-03-01',
    assignee_id: 'u1', description: null, session_id: null,
    created_by: 'u1', created_at: '2026-01-01T00:00:00', updated_at: '2026-01-01T00:00:00',
  },
  {
    id: '2', project_id: 'p1', title: 'Gel electrophoresis',
    priority: 'low', status: 'done', deadline: null,
    assignee_id: null, description: null, session_id: null,
    created_by: 'u1', created_at: '2026-01-02T00:00:00', updated_at: '2026-01-02T00:00:00',
  },
  {
    id: '3', project_id: 'p1', title: 'Western blot protocol',
    priority: 'medium', status: 'in_progress', deadline: '2026-12-31',
    assignee_id: 'u2', description: null, session_id: null,
    created_by: 'u1', created_at: '2026-01-03T00:00:00', updated_at: '2026-01-03T00:00:00',
  },
]

describe('useTaskFilters', () => {
  test('returns all tasks by default', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    expect(result.current.filtered).toHaveLength(3)
  })

  test('filters by search query (case-insensitive)', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    act(() => { result.current.setSearch('pcr') })
    expect(result.current.filtered).toHaveLength(1)
    expect(result.current.filtered[0].id).toBe('1')
  })

  test('empty search returns all tasks', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    act(() => { result.current.setSearch('pcr') })
    act(() => { result.current.setSearch('') })
    expect(result.current.filtered).toHaveLength(3)
  })

  test('filters by priority — deselecting medium and low returns only high', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    act(() => {
      result.current.togglePriority('medium')
      result.current.togglePriority('low')
    })
    expect(result.current.filtered).toHaveLength(1)
    expect(result.current.filtered[0].priority).toBe('high')
  })

  test('deselecting all priorities resets to showing all', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    act(() => {
      result.current.togglePriority('high')
      result.current.togglePriority('medium')
      result.current.togglePriority('low')
    })
    expect(result.current.filtered).toHaveLength(3)
  })

  test('filters by assignee id', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    act(() => { result.current.setAssigneeId('u2') })
    expect(result.current.filtered).toHaveLength(1)
    expect(result.current.filtered[0].id).toBe('3')
  })

  test('assigneeId null returns all', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    act(() => { result.current.setAssigneeId('u1') })
    act(() => { result.current.setAssigneeId(null) })
    expect(result.current.filtered).toHaveLength(3)
  })

  test('sorts by deadline ascending, nulls last', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    act(() => { result.current.setSort('deadline') })
    expect(result.current.filtered[0].id).toBe('1')  // 2026-03-01
    expect(result.current.filtered[1].id).toBe('3')  // 2026-12-31
    expect(result.current.filtered[2].id).toBe('2')  // null → last
  })

  test('sorts by priority: high < medium < low', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    act(() => { result.current.setSort('priority') })
    expect(result.current.filtered[0].priority).toBe('high')
    expect(result.current.filtered[1].priority).toBe('medium')
    expect(result.current.filtered[2].priority).toBe('low')
  })
})
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd EvoScientist/pm/frontend && npm test -- --run hooks/__tests__/useTaskFilters
```

Expected: FAIL — `Cannot find module '../useTaskFilters'`

- [ ] **Step 3: Implement the hook**

Create `EvoScientist/pm/frontend/src/hooks/useTaskFilters.ts`:

```typescript
import { useMemo, useState } from 'react'
import { Task } from '../api'

export type SortKey = 'created' | 'deadline' | 'priority'
export type PrioritySet = Set<Task['priority']>

const ALL_PRIORITIES: Task['priority'][] = ['high', 'medium', 'low']
const PRIORITY_ORDER: Record<Task['priority'], number> = { high: 0, medium: 1, low: 2 }

export function useTaskFilters(tasks: Task[]) {
  const [search, setSearch] = useState('')
  const [priorities, setPriorities] = useState<PrioritySet>(new Set(ALL_PRIORITIES))
  const [sort, setSort] = useState<SortKey>('created')
  const [assigneeId, setAssigneeId] = useState<string | null>(null)

  const filtered = useMemo(() => {
    let result = tasks

    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(t => t.title.toLowerCase().includes(q))
    }

    if (priorities.size < ALL_PRIORITIES.length) {
      result = result.filter(t => priorities.has(t.priority))
    }

    if (assigneeId !== null) {
      result = result.filter(t => t.assignee_id === assigneeId)
    }

    return [...result].sort((a, b) => {
      if (sort === 'priority') {
        return PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]
      }
      if (sort === 'deadline') {
        if (!a.deadline && !b.deadline) return 0
        if (!a.deadline) return 1
        if (!b.deadline) return -1
        return a.deadline.localeCompare(b.deadline)
      }
      // default: created
      return a.created_at.localeCompare(b.created_at)
    })
  }, [tasks, search, priorities, sort, assigneeId])

  function togglePriority(p: Task['priority']) {
    setPriorities(prev => {
      const next = new Set(prev)
      if (next.has(p)) {
        next.delete(p)
      } else {
        next.add(p)
      }
      return next.size === 0 ? new Set(ALL_PRIORITIES) : next
    })
  }

  return { search, setSearch, priorities, togglePriority, sort, setSort, assigneeId, setAssigneeId, filtered }
}
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
cd EvoScientist/pm/frontend && npm test -- --run hooks/__tests__/useTaskFilters
```

Expected: PASS — 9 tests, 0 failures.

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/frontend/src/hooks/
git commit -m "feat(pm): add useTaskFilters hook with tests"
```

---

## Task 3: Create `FilterToolbar` component

**Files:**
- Create: `EvoScientist/pm/frontend/src/components/FilterToolbar.tsx`
- Create: `EvoScientist/pm/frontend/src/components/__tests__/FilterToolbar.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `EvoScientist/pm/frontend/src/components/__tests__/FilterToolbar.test.tsx`:

```typescript
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi, beforeEach } from 'vitest'
import { FilterToolbar } from '../FilterToolbar'
import { Member, Task } from '../../api'

const MEMBERS: Member[] = [
  { user_id: 'u1', username: 'dr_chen', role: 'owner', added_at: '' },
  { user_id: 'u2', username: 'lab_tech', role: 'editor', added_at: '' },
]

const defaultProps = {
  search: '',
  onSearchChange: vi.fn(),
  priorities: new Set<Task['priority']>(['high', 'medium', 'low']),
  onTogglePriority: vi.fn(),
  sort: 'created' as const,
  onSortChange: vi.fn(),
  assigneeId: null,
  onAssigneeChange: vi.fn(),
  members: MEMBERS,
}

beforeEach(() => { vi.clearAllMocks() })

describe('FilterToolbar', () => {
  test('renders the search input', () => {
    render(<FilterToolbar {...defaultProps} />)
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument()
  })

  test('calls onSearchChange when typing in search', () => {
    render(<FilterToolbar {...defaultProps} />)
    fireEvent.change(screen.getByPlaceholderText(/search/i), { target: { value: 'pcr' } })
    expect(defaultProps.onSearchChange).toHaveBeenCalledWith('pcr')
  })

  test('renders CRIT, NORM, ROUT priority buttons', () => {
    render(<FilterToolbar {...defaultProps} />)
    expect(screen.getByText('CRIT')).toBeInTheDocument()
    expect(screen.getByText('NORM')).toBeInTheDocument()
    expect(screen.getByText('ROUT')).toBeInTheDocument()
  })

  test('calls onTogglePriority("high") when CRIT button clicked', () => {
    render(<FilterToolbar {...defaultProps} />)
    fireEvent.click(screen.getByText('CRIT'))
    expect(defaultProps.onTogglePriority).toHaveBeenCalledWith('high')
  })

  test('calls onTogglePriority("medium") when NORM clicked', () => {
    render(<FilterToolbar {...defaultProps} />)
    fireEvent.click(screen.getByText('NORM'))
    expect(defaultProps.onTogglePriority).toHaveBeenCalledWith('medium')
  })

  test('renders member names in assignee dropdown', () => {
    render(<FilterToolbar {...defaultProps} />)
    expect(screen.getByText('dr_chen')).toBeInTheDocument()
    expect(screen.getByText('lab_tech')).toBeInTheDocument()
  })

  test('calls onAssigneeChange with user_id when member selected', () => {
    render(<FilterToolbar {...defaultProps} />)
    const select = screen.getByDisplayValue('Researcher: All')
    fireEvent.change(select, { target: { value: 'u1' } })
    expect(defaultProps.onAssigneeChange).toHaveBeenCalledWith('u1')
  })

  test('calls onAssigneeChange with null when "All" selected', () => {
    render(<FilterToolbar {...defaultProps} assigneeId="u1" />)
    const select = screen.getByDisplayValue('dr_chen')
    fireEvent.change(select, { target: { value: '' } })
    expect(defaultProps.onAssigneeChange).toHaveBeenCalledWith(null)
  })
})
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd EvoScientist/pm/frontend && npm test -- --run components/__tests__/FilterToolbar
```

Expected: FAIL — `Cannot find module '../FilterToolbar'`

- [ ] **Step 3: Create the component**

Create `EvoScientist/pm/frontend/src/components/FilterToolbar.tsx`:

```typescript
import React from 'react'
import { Task, Member } from '../api'
import { SortKey, PrioritySet } from '../hooks/useTaskFilters'

interface Props {
  search: string
  onSearchChange: (v: string) => void
  priorities: PrioritySet
  onTogglePriority: (p: Task['priority']) => void
  sort: SortKey
  onSortChange: (s: SortKey) => void
  assigneeId: string | null
  onAssigneeChange: (id: string | null) => void
  members: Member[]
}

// Lab-context display labels
const PRIORITY_LABELS: Record<Task['priority'], string> = {
  high: 'CRIT',
  medium: 'NORM',
  low: 'ROUT',
}

const PRIORITY_COLORS: Record<Task['priority'], string> = {
  high: '#f43f5e',
  medium: '#f59e0b',
  low: '#22c55e',
}

const PRIORITY_GLOW: Record<Task['priority'], string> = {
  high: '244,63,94',
  medium: '245,158,11',
  low: '34,197,94',
}

export function FilterToolbar({
  search, onSearchChange,
  priorities, onTogglePriority,
  sort, onSortChange,
  assigneeId, onAssigneeChange,
  members,
}: Props) {
  return (
    <div style={{
      padding: '6px 20px',
      borderBottom: '1px solid rgba(100,140,200,0.07)',
      background: 'rgba(7,11,18,0.55)',
      display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
      flexShrink: 0,
    }}>
      <input
        placeholder="🔬 Search experiments…"
        value={search}
        onChange={e => onSearchChange(e.target.value)}
        style={{
          flex: '1 1 160px', maxWidth: 260, padding: '5px 10px',
          background: 'rgba(13,21,38,0.8)',
          border: '1px solid rgba(100,140,200,0.12)',
          borderRadius: 6, color: '#e2e8f0', fontSize: 12, outline: 'none',
        }}
      />

      <div style={{ display: 'flex', gap: 5 }}>
        {(['high', 'medium', 'low'] as Task['priority'][]).map(p => {
          const active = priorities.has(p)
          return (
            <button
              key={p}
              onClick={() => onTogglePriority(p)}
              style={{
                padding: '4px 9px', fontSize: 10, fontWeight: 700,
                cursor: 'pointer', borderRadius: 4, letterSpacing: '0.08em',
                fontFamily: 'var(--font-mono)',
                background: active
                  ? `rgba(${PRIORITY_GLOW[p]},0.12)`
                  : 'rgba(100,140,200,0.05)',
                border: `1px solid ${active ? PRIORITY_COLORS[p] + '40' : 'rgba(100,140,200,0.12)'}`,
                color: active ? PRIORITY_COLORS[p] : '#334155',
                transition: 'all 0.14s',
              }}
            >
              {PRIORITY_LABELS[p]}
            </button>
          )
        })}
      </div>

      <select
        value={sort}
        onChange={e => onSortChange(e.target.value as SortKey)}
        style={{
          padding: '5px 8px',
          background: 'rgba(13,21,38,0.8)',
          border: '1px solid rgba(100,140,200,0.12)',
          borderRadius: 6, color: '#94a3b8', fontSize: 11, outline: 'none',
          cursor: 'pointer', fontFamily: 'var(--font-mono)',
        }}
      >
        <option value="created">Sort: Added</option>
        <option value="deadline">Sort: Deadline</option>
        <option value="priority">Sort: Priority</option>
      </select>

      <select
        value={assigneeId ?? ''}
        onChange={e => onAssigneeChange(e.target.value || null)}
        style={{
          padding: '5px 8px',
          background: 'rgba(13,21,38,0.8)',
          border: '1px solid rgba(100,140,200,0.12)',
          borderRadius: 6, color: '#94a3b8', fontSize: 11, outline: 'none',
          cursor: 'pointer', fontFamily: 'var(--font-mono)',
        }}
      >
        <option value="">Researcher: All</option>
        {members.map(m => (
          <option key={m.user_id} value={m.user_id}>{m.username}</option>
        ))}
      </select>
    </div>
  )
}
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
cd EvoScientist/pm/frontend && npm test -- --run components/__tests__/FilterToolbar
```

Expected: PASS — 8 tests, 0 failures.

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/frontend/src/components/FilterToolbar.tsx \
        EvoScientist/pm/frontend/src/components/__tests__/FilterToolbar.test.tsx
git commit -m "feat(pm): add FilterToolbar component with lab-context labels"
```

---

## Task 4: Create `CardEditPopover` component

**Files:**
- Create: `EvoScientist/pm/frontend/src/components/CardEditPopover.tsx`
- Create: `EvoScientist/pm/frontend/src/components/__tests__/CardEditPopover.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `EvoScientist/pm/frontend/src/components/__tests__/CardEditPopover.test.tsx`:

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, test, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { CardEditPopover } from '../CardEditPopover'
import { Task } from '../../api'
import * as apiModule from '../../api'

const TASK: Task = {
  id: 't1', project_id: 'p1', title: 'PCR baseline run',
  priority: 'high', status: 'todo', deadline: '2026-06-01',
  assignee_id: null, description: null, session_id: null,
  created_by: 'u1', created_at: '2026-01-01T00:00:00', updated_at: '2026-01-01T00:00:00',
}

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      {children}
    </QueryClientProvider>
  )
}

beforeEach(() => { vi.clearAllMocks() })

describe('CardEditPopover', () => {
  test('renders with task title pre-filled', () => {
    render(
      <CardEditPopover task={TASK} projectId="p1" onClose={vi.fn()} />,
      { wrapper }
    )
    expect(screen.getByDisplayValue('PCR baseline run')).toBeInTheDocument()
  })

  test('renders with task priority pre-selected', () => {
    render(
      <CardEditPopover task={TASK} projectId="p1" onClose={vi.fn()} />,
      { wrapper }
    )
    expect(screen.getByDisplayValue('High')).toBeInTheDocument()
  })

  test('calls onClose when ESC key pressed', () => {
    const onClose = vi.fn()
    render(
      <CardEditPopover task={TASK} projectId="p1" onClose={onClose} />,
      { wrapper }
    )
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })

  test('calls updateTask and onClose when SAVE clicked', async () => {
    vi.spyOn(apiModule.api, 'updateTask').mockResolvedValue({ ...TASK, title: 'Updated' })
    const onClose = vi.fn()
    render(
      <CardEditPopover task={TASK} projectId="p1" onClose={onClose} />,
      { wrapper }
    )
    fireEvent.click(screen.getByText('SAVE'))
    await waitFor(() => expect(apiModule.api.updateTask).toHaveBeenCalledWith(
      'p1', 't1', expect.objectContaining({ title: 'PCR baseline run' })
    ))
  })

  test('calls onClose when ✕ button clicked', () => {
    const onClose = vi.fn()
    render(
      <CardEditPopover task={TASK} projectId="p1" onClose={onClose} />,
      { wrapper }
    )
    fireEvent.click(screen.getByText('✕'))
    expect(onClose).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd EvoScientist/pm/frontend && npm test -- --run components/__tests__/CardEditPopover
```

Expected: FAIL — `Cannot find module '../CardEditPopover'`

- [ ] **Step 3: Create the component**

Create `EvoScientist/pm/frontend/src/components/CardEditPopover.tsx`:

```typescript
import React, { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Task } from '../api'

interface Props {
  task: Task
  projectId: string
  onClose: () => void
}

export function CardEditPopover({ task, projectId, onClose }: Props) {
  const queryClient = useQueryClient()
  const ref = useRef<HTMLDivElement>(null)
  const [title, setTitle] = useState(task.title)
  const [priority, setPriority] = useState<Task['priority']>(task.priority)
  const [deadline, setDeadline] = useState(task.deadline ?? '')

  const updateTask = useMutation({
    mutationFn: (data: Partial<Task>) => api.updateTask(projectId, task.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      onClose()
    },
  })

  function handleSave() {
    updateTask.mutate({ title, priority, deadline: deadline || null })
  }

  // Close on outside click
  useEffect(() => {
    function onMouseDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => document.removeEventListener('mousedown', onMouseDown)
  }, [onClose])

  // Close on Escape
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  return (
    <div
      ref={ref}
      style={{
        position: 'fixed',
        top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)',
        zIndex: 200,
        background: 'var(--surface)',
        border: '1px solid rgba(34,211,238,0.25)',
        borderRadius: 10, padding: 16, width: 280,
        boxShadow: '0 16px 48px rgba(0,0,0,0.55)',
        animation: 'fadeInUp 0.15s ease',
      }}
    >
      <div style={{
        fontSize: 9, color: '#22d3ee', fontWeight: 700,
        letterSpacing: '0.1em', marginBottom: 12,
        fontFamily: 'var(--font-mono)',
      }}>
        QUICK EDIT · LAB TASK
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
        <input
          autoFocus
          value={title}
          onChange={e => setTitle(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSave()}
          style={{
            padding: '8px 10px',
            background: 'rgba(7,11,18,0.7)',
            border: '1px solid rgba(34,211,238,0.25)',
            borderRadius: 6, color: '#e2e8f0', fontSize: 13, outline: 'none',
          }}
        />

        <div style={{ display: 'flex', gap: 7 }}>
          <select
            value={priority}
            onChange={e => setPriority(e.target.value as Task['priority'])}
            style={{
              flex: 1, padding: '6px 8px',
              background: 'rgba(7,11,18,0.7)',
              border: '1px solid rgba(100,140,200,0.14)',
              borderRadius: 6, color: '#94a3b8', fontSize: 11, outline: 'none',
              fontFamily: 'var(--font-mono)',
            }}
          >
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>

          <input
            type="date"
            value={deadline}
            onChange={e => setDeadline(e.target.value)}
            style={{
              flex: 1, padding: '6px 8px',
              background: 'rgba(7,11,18,0.7)',
              border: '1px solid rgba(100,140,200,0.14)',
              borderRadius: 6, color: '#94a3b8', fontSize: 11, outline: 'none',
            }}
          />
        </div>

        <div style={{ display: 'flex', gap: 6, marginTop: 2 }}>
          <button
            onClick={handleSave}
            disabled={updateTask.isPending}
            style={{
              flex: 1, padding: '7px',
              background: 'rgba(34,211,238,0.12)',
              border: '1px solid rgba(34,211,238,0.28)',
              borderRadius: 6, color: '#22d3ee',
              fontSize: 10, fontWeight: 700, cursor: 'pointer',
              fontFamily: 'var(--font-mono)',
              opacity: updateTask.isPending ? 0.6 : 1,
            }}
          >{updateTask.isPending ? '…' : 'SAVE'}</button>
          <button
            onClick={onClose}
            style={{
              padding: '7px 12px',
              background: 'rgba(100,140,200,0.07)',
              border: '1px solid rgba(100,140,200,0.12)',
              borderRadius: 6, color: '#475569',
              fontSize: 10, cursor: 'pointer',
            }}
          >✕</button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
cd EvoScientist/pm/frontend && npm test -- --run components/__tests__/CardEditPopover
```

Expected: PASS — 5 tests, 0 failures.

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/frontend/src/components/CardEditPopover.tsx \
        EvoScientist/pm/frontend/src/components/__tests__/CardEditPopover.test.tsx
git commit -m "feat(pm): add CardEditPopover component with tests"
```

---

## Task 5: Rewrite `Board.tsx` with DnD, FilterToolbar, hover icon, and overdue highlighting

**Files:**
- Modify: `EvoScientist/pm/frontend/src/pages/Board.tsx`

**Context:** The current Board.tsx is at `EvoScientist/pm/frontend/src/pages/Board.tsx`. Read it before editing. The columns constant is near the top, tasks are fetched with TanStack Query, the layout is a flex row of three column divs.

**Lab context display labels used in this file:**
- Column "todo" → label `PLANNED`
- Column "in_progress" → label `IN PROGRESS`
- Column "done" → label `COMPLETE`
- Priority dot labels: `CRIT` / `NORM` / `ROUT`

- [ ] **Step 1: Write the complete new Board.tsx**

Replace the entire file content with:

```typescript
import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  DndContext, DragEndEvent, DragOverEvent, DragStartEvent,
  PointerSensor, useSensor, useSensors, useDroppable, useDraggable,
} from '@dnd-kit/core'
import { api, Task } from '../api'
import { TaskDetail } from './TaskDetail'
import { FilterToolbar } from '../components/FilterToolbar'
import { CardEditPopover } from '../components/CardEditPopover'
import { useTaskFilters } from '../hooks/useTaskFilters'

const COLUMNS: { key: Task['status']; label: string; accent: string; glow: string; dimBg: string }[] = [
  { key: 'todo',        label: 'PLANNED',     accent: '#22d3ee', glow: '34,211,238',  dimBg: 'rgba(34,211,238,0.04)'  },
  { key: 'in_progress', label: 'IN PROGRESS', accent: '#f59e0b', glow: '245,158,11',  dimBg: 'rgba(245,158,11,0.04)'  },
  { key: 'done',        label: 'COMPLETE',    accent: '#10b981', glow: '16,185,129',  dimBg: 'rgba(16,185,129,0.04)'  },
]

const PRIORITY: Record<string, { color: string; label: string }> = {
  high:   { color: '#f43f5e', label: 'CRIT' },
  medium: { color: '#f59e0b', label: 'NORM' },
  low:    { color: '#22c55e', label: 'ROUT' },
}

const AVATAR_COLORS = ['#6366f1', '#ec4899', '#f59e0b', '#22d3ee', '#10b981', '#8b5cf6']

function isOverdue(deadline: string | null): boolean {
  if (!deadline) return false
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return new Date(deadline) < today
}

// ── Droppable column wrapper ──────────────────────────────────────────────────

interface DroppableProps {
  colKey: Task['status']
  accent: string
  glow: string
  dimBg: string
  isOver: boolean
  children: React.ReactNode
}

function DroppableColumn({ colKey, accent, glow, dimBg, isOver, children }: DroppableProps) {
  const { setNodeRef } = useDroppable({ id: colKey })
  return (
    <div
      ref={setNodeRef}
      style={{
        flex: '0 0 290px',
        background: isOver ? `rgba(${glow},0.07)` : 'rgba(13,21,38,0.55)',
        border: isOver
          ? `2px solid ${accent}`
          : '1px solid rgba(100,140,200,0.09)',
        borderTop: `2px solid ${accent}`,
        borderRadius: '0 0 10px 10px',
        display: 'flex', flexDirection: 'column',
        maxHeight: 'calc(100vh - 140px)',
        overflow: 'hidden',
        transition: 'background 0.15s, border-color 0.15s',
        boxShadow: isOver ? `0 0 18px rgba(${glow},0.18)` : 'none',
      }}
    >
      {children}
    </div>
  )
}

// ── Draggable task card ───────────────────────────────────────────────────────

interface CardProps {
  task: Task
  col: typeof COLUMNS[0]
  onOpen: () => void
  onEdit: () => void
}

function DraggableCard({ task, col, onOpen, onEdit }: CardProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: task.id })
  const [isHovered, setIsHovered] = useState(false)
  const p = PRIORITY[task.priority] ?? PRIORITY.low
  const overdue = isOverdue(task.deadline)

  return (
    <div
      ref={setNodeRef}
      style={{
        position: 'relative',
        transform: transform ? `translate(${transform.x}px, ${transform.y}px)` : undefined,
        opacity: isDragging ? 0.35 : 1,
        zIndex: isDragging ? 50 : 'auto',
        cursor: isDragging ? 'grabbing' : 'grab',
      }}
      {...attributes}
      {...listeners}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div
        onClick={() => !isDragging && onOpen()}
        style={{
          background: 'rgba(17,30,53,0.75)',
          border: '1px solid rgba(100,140,200,0.09)',
          borderLeft: overdue ? '3px solid #f43f5e' : undefined,
          borderRadius: 7, padding: '11px 13px',
          transition: 'transform 0.14s, border-color 0.14s, box-shadow 0.14s',
        }}
        onMouseEnter={e => {
          if (!isDragging) {
            const el = e.currentTarget
            el.style.transform = 'translateY(-2px)'
            el.style.borderColor = `rgba(${col.glow},0.3)`
            el.style.boxShadow = `0 5px 18px rgba(0,0,0,0.28)`
          }
        }}
        onMouseLeave={e => {
          const el = e.currentTarget
          el.style.transform = ''
          el.style.borderColor = 'rgba(100,140,200,0.09)'
          el.style.boxShadow = ''
        }}
      >
        <p style={{ margin: '0 0 9px', fontWeight: 500, fontSize: 13, lineHeight: 1.4, color: '#dde5f0', paddingRight: 20 }}>
          {task.title}
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
            background: p.color, boxShadow: `0 0 5px ${p.color}88`,
          }} />
          <span style={{ fontSize: 9, fontWeight: 700, color: p.color, letterSpacing: '0.1em', fontFamily: 'var(--font-mono)' }}>
            {p.label}
          </span>
          {task.deadline && (
            <span style={{
              marginLeft: 'auto', fontSize: 9, fontFamily: 'var(--font-mono)',
              color: overdue ? '#f43f5e' : '#3d4e64',
            }}>
              {task.deadline}
            </span>
          )}
        </div>
      </div>

      {/* Hover edit button — stops drag listener propagation via onPointerDown */}
      {isHovered && !isDragging && (
        <button
          onPointerDown={e => e.stopPropagation()}
          onClick={e => { e.stopPropagation(); onEdit() }}
          style={{
            position: 'absolute', top: 6, right: 6,
            background: 'rgba(34,211,238,0.1)',
            border: '1px solid rgba(34,211,238,0.25)',
            borderRadius: 4, color: '#22d3ee',
            width: 22, height: 22, fontSize: 11,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', zIndex: 5,
          }}
        >✎</button>
      )}
    </div>
  )
}

// ── Board ─────────────────────────────────────────────────────────────────────

export function Board() {
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [editPopoverTask, setEditPopoverTask] = useState<Task | null>(null)
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [addingToCol, setAddingToCol] = useState<Task['status'] | null>(null)
  const [activeTask, setActiveTask] = useState<Task | null>(null)
  const [overColumnKey, setOverColumnKey] = useState<Task['status'] | null>(null)

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.getProject(projectId!),
  })

  const { data: tasks = [] } = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => api.listTasks(projectId!),
    refetchInterval: 15_000,
  })

  const filters = useTaskFilters(tasks)

  const createTask = useMutation({
    mutationFn: (title: string) =>
      api.createTask(projectId!, { title, status: addingToCol ?? 'todo' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      setNewTaskTitle('')
      setAddingToCol(null)
    },
  })

  const updateTask = useMutation({
    mutationFn: ({ taskId, data }: { taskId: string; data: Partial<Task> }) =>
      api.updateTask(projectId!, taskId, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks', projectId] }),
  })

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  )

  function handleDragStart(event: DragStartEvent) {
    const task = tasks.find(t => t.id === String(event.active.id))
    setActiveTask(task ?? null)
  }

  function handleDragOver(event: DragOverEvent) {
    const colKey = event.over?.id as Task['status'] | null
    setOverColumnKey(colKey ?? null)
  }

  function handleDragEnd(event: DragEndEvent) {
    if (activeTask && overColumnKey && overColumnKey !== activeTask.status) {
      updateTask.mutate({ taskId: activeTask.id, data: { status: overColumnKey } })
    }
    setActiveTask(null)
    setOverColumnKey(null)
  }

  return (
    <div style={{ background: 'var(--bg)', height: '100vh', display: 'flex', flexDirection: 'column', color: 'var(--text)' }}>

      {/* Header */}
      <div style={{
        padding: '0 24px', height: 52, flexShrink: 0,
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 14,
        background: 'rgba(13,21,38,0.85)', backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <button
          onClick={() => navigate('/projects')}
          style={{
            cursor: 'pointer', background: 'rgba(100,140,200,0.07)',
            border: '1px solid rgba(100,140,200,0.14)', borderRadius: 6,
            color: '#64748b', padding: '3px 9px', fontSize: 15, lineHeight: 1,
            transition: 'color 0.15s, border-color 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.color = '#22d3ee'; e.currentTarget.style.borderColor = 'rgba(34,211,238,0.3)' }}
          onMouseLeave={e => { e.currentTarget.style.color = '#64748b'; e.currentTarget.style.borderColor = 'rgba(100,140,200,0.14)' }}
        >←</button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22d3ee', boxShadow: '0 0 6px #22d3ee', flexShrink: 0 }} />
          <h1 style={{ margin: 0, fontSize: 14, fontWeight: 600, letterSpacing: '0.03em', color: '#f1f5f9', fontFamily: 'var(--font-mono)' }}>
            {project?.name ?? '…'}
          </h1>
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 5 }}>
          {project?.members.map((m, i) => (
            <span key={m.user_id} title={`${m.username} (${m.role})`} style={{
              width: 26, height: 26, borderRadius: '50%',
              background: AVATAR_COLORS[i % AVATAR_COLORS.length],
              color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 10, fontWeight: 700,
              border: '2px solid rgba(7,11,18,0.9)',
              fontFamily: 'var(--font-mono)', cursor: 'default',
            }}>
              {m.username[0].toUpperCase()}
            </span>
          ))}
        </div>
      </div>

      {/* Filter toolbar */}
      <FilterToolbar
        search={filters.search}
        onSearchChange={filters.setSearch}
        priorities={filters.priorities}
        onTogglePriority={filters.togglePriority}
        sort={filters.sort}
        onSortChange={filters.setSort}
        assigneeId={filters.assigneeId}
        onAssigneeChange={filters.setAssigneeId}
        members={project?.members ?? []}
      />

      {/* Kanban columns */}
      <DndContext sensors={sensors} onDragStart={handleDragStart} onDragOver={handleDragOver} onDragEnd={handleDragEnd}>
        <div style={{ display: 'flex', flex: 1, overflowX: 'auto', padding: '16px 20px', gap: 16, alignItems: 'flex-start' }}>
          {COLUMNS.map(col => {
            const colTasks = filters.filtered.filter(t => t.status === col.key)
            const isOver = overColumnKey === col.key

            return (
              <DroppableColumn key={col.key} colKey={col.key} accent={col.accent} glow={col.glow} dimBg={col.dimBg} isOver={isOver}>
                {/* Column header */}
                <div style={{
                  padding: '11px 13px 9px',
                  background: col.dimBg,
                  borderBottom: '1px solid rgba(100,140,200,0.07)',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  flexShrink: 0,
                }}>
                  <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', color: col.accent, fontFamily: 'var(--font-mono)' }}>
                    {col.label}
                  </span>
                  <span style={{
                    fontSize: 10, fontWeight: 700, color: col.accent,
                    background: `rgba(${col.glow},0.1)`,
                    border: `1px solid rgba(${col.glow},0.22)`,
                    borderRadius: 9, padding: '1px 7px', fontFamily: 'var(--font-mono)',
                  }}>
                    {colTasks.length}
                  </span>
                </div>

                {/* Cards */}
                <div style={{ flex: 1, overflowY: 'auto', padding: '8px 9px 4px', display: 'flex', flexDirection: 'column', gap: 7 }}>
                  {colTasks.map(task => (
                    <DraggableCard
                      key={task.id}
                      task={task}
                      col={col}
                      onOpen={() => setSelectedTask(task)}
                      onEdit={() => setEditPopoverTask(task)}
                    />
                  ))}
                  {/* Ghost placeholder shown when dragging over this column */}
                  {isOver && activeTask && activeTask.status !== col.key && (
                    <div style={{
                      height: 46,
                      border: `1px dashed rgba(${col.glow},0.4)`,
                      borderRadius: 7,
                      background: `rgba(${col.glow},0.04)`,
                      flexShrink: 0,
                    }} />
                  )}
                </div>

                {/* Add task footer */}
                <div style={{ padding: '6px 9px 9px', flexShrink: 0 }}>
                  {addingToCol === col.key ? (
                    <form onSubmit={e => { e.preventDefault(); createTask.mutate(newTaskTitle) }}>
                      <input
                        autoFocus value={newTaskTitle}
                        onChange={e => setNewTaskTitle(e.target.value)}
                        placeholder="Experiment or task title…" required
                        style={{
                          width: '100%', padding: '7px 10px', boxSizing: 'border-box', marginBottom: 5,
                          background: 'rgba(7,11,18,0.65)',
                          border: `1px solid rgba(${col.glow},0.3)`,
                          borderRadius: 6, color: '#e2e8f0', fontSize: 12, outline: 'none',
                        }}
                      />
                      <div style={{ display: 'flex', gap: 4 }}>
                        <button type="submit" style={{
                          flex: 1, padding: '5px 0', fontSize: 11, cursor: 'pointer',
                          background: col.accent, color: '#070b12', border: 'none', borderRadius: 5, fontWeight: 700, fontFamily: 'var(--font-mono)',
                        }}>ADD</button>
                        <button type="button" onClick={() => setAddingToCol(null)} style={{
                          padding: '5px 9px', fontSize: 11, cursor: 'pointer',
                          background: 'rgba(100,140,200,0.07)', border: '1px solid rgba(100,140,200,0.14)', borderRadius: 5, color: '#64748b',
                        }}>✕</button>
                      </div>
                    </form>
                  ) : (
                    <button
                      onClick={() => setAddingToCol(col.key)}
                      style={{
                        width: '100%', background: 'none',
                        border: `1px dashed rgba(${col.glow},0.2)`,
                        borderRadius: 6, padding: '7px 10px',
                        cursor: 'pointer', color: '#3d4e64',
                        fontSize: 11, textAlign: 'left',
                        transition: 'border-color 0.14s, color 0.14s',
                      }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = `rgba(${col.glow},0.45)`; e.currentTarget.style.color = col.accent }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = `rgba(${col.glow},0.2)`; e.currentTarget.style.color = '#3d4e64' }}
                    >+ Add experiment / task</button>
                  )}
                </div>
              </DroppableColumn>
            )
          })}
        </div>
      </DndContext>

      {editPopoverTask && (
        <CardEditPopover
          task={editPopoverTask}
          projectId={projectId!}
          onClose={() => setEditPopoverTask(null)}
        />
      )}

      {selectedTask && (
        <TaskDetail
          task={selectedTask}
          projectId={projectId!}
          members={project?.members ?? []}
          onClose={() => setSelectedTask(null)}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Run the build — expect success**

```bash
cd EvoScientist/pm/frontend && npm run build
```

Expected: `✓ built in ...ms` — no TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add EvoScientist/pm/frontend/src/pages/Board.tsx
git commit -m "feat(pm): rewrite Board with DnD, filter toolbar, lab labels, overdue highlighting"
```

---

## Task 6: Update `TaskDetail.tsx` — edit mode, assignee, delete, overdue badge

**Files:**
- Modify: `EvoScientist/pm/frontend/src/pages/TaskDetail.tsx`

**Context:** Read the current file first. The Props interface is `{ task: Task, projectId: string, onClose: () => void }`. You must add `members: Member[]` to it. Board.tsx (updated in Task 5) already passes `members={project?.members ?? []}`.

**Lab context labels:** Status options use human-readable text (`Planned` / `In Progress` / `Complete`); displayed badges use `PLANNED` / `IN PROGRESS` / `COMPLETE`.

- [ ] **Step 1: Write the complete new TaskDetail.tsx**

Replace the entire file with:

```typescript
import React, { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Task, Member } from '../api'

interface Props {
  task: Task
  projectId: string
  members: Member[]
  onClose: () => void
}

const STATUS_STYLE: Record<Task['status'], { color: string; bg: string; label: string }> = {
  todo:        { color: '#22d3ee', bg: 'rgba(34,211,238,0.08)',  label: 'PLANNED'     },
  in_progress: { color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', label: 'IN PROGRESS' },
  done:        { color: '#10b981', bg: 'rgba(16,185,129,0.08)', label: 'COMPLETE'    },
}

const PRIORITY_STYLE: Record<Task['priority'], { color: string; bg: string; label: string }> = {
  high:   { color: '#f43f5e', bg: 'rgba(244,63,94,0.1)',  label: 'CRITICAL' },
  medium: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', label: 'STANDARD' },
  low:    { color: '#22c55e', bg: 'rgba(34,197,94,0.1)',  label: 'ROUTINE'  },
}

function isOverdue(deadline: string | null): boolean {
  if (!deadline) return false
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return new Date(deadline) < today
}

export function TaskDetail({ task, projectId, members, onClose }: Props) {
  const queryClient = useQueryClient()
  const deleteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // View state
  const [commentBody, setCommentBody] = useState('')
  const [copied, setCopied] = useState(false)

  // Edit state
  const [isEditing, setIsEditing] = useState(false)
  const [editTitle, setEditTitle] = useState(task.title)
  const [editStatus, setEditStatus] = useState<Task['status']>(task.status)
  const [editPriority, setEditPriority] = useState<Task['priority']>(task.priority)
  const [editDeadline, setEditDeadline] = useState(task.deadline ?? '')
  const [editDescription, setEditDescription] = useState(task.description ?? '')
  const [editAssigneeId, setEditAssigneeId] = useState(task.assignee_id ?? '')
  const [deleteConfirm, setDeleteConfirm] = useState(false)

  const { data: comments = [] } = useQuery({
    queryKey: ['comments', task.id],
    queryFn: () => api.listComments(projectId, task.id),
  })

  const addComment = useMutation({
    mutationFn: (body: string) => api.addComment(projectId, task.id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comments', task.id] })
      setCommentBody('')
    },
  })

  const updateTask = useMutation({
    mutationFn: (data: Partial<Task>) => api.updateTask(projectId, task.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      setIsEditing(false)
    },
  })

  const deleteTask = useMutation({
    mutationFn: () => api.deleteTask(projectId, task.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      onClose()
    },
  })

  function handleSave() {
    updateTask.mutate({
      title: editTitle,
      status: editStatus,
      priority: editPriority,
      deadline: editDeadline || null,
      description: editDescription || null,
      assignee_id: editAssigneeId || null,
    })
  }

  function handleDeleteClick() {
    if (!deleteConfirm) {
      setDeleteConfirm(true)
      deleteTimerRef.current = setTimeout(() => setDeleteConfirm(false), 3000)
    } else {
      if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current)
      deleteTask.mutate()
    }
  }

  function startEdit() {
    setEditTitle(task.title)
    setEditStatus(task.status)
    setEditPriority(task.priority)
    setEditDeadline(task.deadline ?? '')
    setEditDescription(task.description ?? '')
    setEditAssigneeId(task.assignee_id ?? '')
    setDeleteConfirm(false)
    setIsEditing(true)
  }

  const status = STATUS_STYLE[task.status]
  const priority = PRIORITY_STYLE[task.priority]
  const overdue = isOverdue(task.deadline)

  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(7,11,18,0.72)', backdropFilter: 'blur(5px)',
        display: 'flex', justifyContent: 'flex-end', zIndex: 100,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--surface)',
          borderLeft: '1px solid rgba(100,140,200,0.12)',
          width: 476, height: '100%', overflowY: 'auto',
          padding: '28px 28px 32px',
          animation: 'slideInRight 0.2s ease',
          display: 'flex', flexDirection: 'column', gap: 20,
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Title + action buttons */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
          <h2 style={{ flex: 1, margin: 0, fontSize: 16, fontWeight: 600, color: '#f1f5f9', lineHeight: 1.35 }}>
            {task.title}
          </h2>
          <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
            {!isEditing && (
              <button
                onClick={startEdit}
                style={{
                  cursor: 'pointer', background: 'rgba(34,211,238,0.08)',
                  border: '1px solid rgba(34,211,238,0.2)', borderRadius: 6,
                  color: '#22d3ee', padding: '3px 10px',
                  fontSize: 9, fontWeight: 700, letterSpacing: '0.1em',
                  fontFamily: 'var(--font-mono)',
                }}
              >EDIT ✎</button>
            )}
            <button
              onClick={onClose}
              style={{
                cursor: 'pointer', background: 'rgba(100,140,200,0.07)',
                border: '1px solid rgba(100,140,200,0.12)', borderRadius: 6,
                color: '#475569', width: 28, height: 28, fontSize: 14,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'color 0.14s, border-color 0.14s',
              }}
              onMouseEnter={e => { e.currentTarget.style.color = '#f43f5e'; e.currentTarget.style.borderColor = 'rgba(244,63,94,0.28)' }}
              onMouseLeave={e => { e.currentTarget.style.color = '#475569'; e.currentTarget.style.borderColor = 'rgba(100,140,200,0.12)' }}
            >✕</button>
          </div>
        </div>

        {/* Badges (view mode) / Form fields (edit mode) */}
        {!isEditing ? (
          <>
            <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
              <span style={{ padding: '3px 10px', borderRadius: 4, background: status.bg, border: `1px solid ${status.color}28`, color: status.color, fontSize: 9, fontWeight: 700, letterSpacing: '0.12em', fontFamily: 'var(--font-mono)' }}>
                {status.label}
              </span>
              <span style={{ padding: '3px 10px', borderRadius: 4, background: priority.bg, border: `1px solid ${priority.color}28`, color: priority.color, fontSize: 9, fontWeight: 700, letterSpacing: '0.12em', fontFamily: 'var(--font-mono)' }}>
                {priority.label}
              </span>
              {task.deadline && (
                <span style={{
                  padding: '3px 10px', borderRadius: 4,
                  background: overdue ? 'rgba(244,63,94,0.12)' : 'rgba(100,140,200,0.07)',
                  border: `1px solid ${overdue ? 'rgba(244,63,94,0.28)' : 'rgba(100,140,200,0.12)'}`,
                  color: overdue ? '#f43f5e' : '#94a3b8',
                  fontSize: 9, fontWeight: 500, fontFamily: 'var(--font-mono)',
                }}>
                  {overdue ? '⚠ OVERDUE · ' : '⏱ '}{task.deadline}
                </span>
              )}
              {task.assignee_id && members.find(m => m.user_id === task.assignee_id) && (
                <span style={{ padding: '3px 10px', borderRadius: 4, background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.22)', color: '#818cf8', fontSize: 9, fontWeight: 500, fontFamily: 'var(--font-mono)' }}>
                  👤 {members.find(m => m.user_id === task.assignee_id)?.username}
                </span>
              )}
            </div>

            <div style={{ height: 1, background: 'rgba(100,140,200,0.07)', flexShrink: 0 }} />

            {task.description && (
              <p style={{ margin: 0, color: '#94a3b8', fontSize: 13, lineHeight: 1.65 }}>{task.description}</p>
            )}
          </>
        ) : (
          /* Edit form */
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div>
              <label style={{ display: 'block', fontSize: 9, fontWeight: 700, color: '#3d4e64', letterSpacing: '0.1em', marginBottom: 5, fontFamily: 'var(--font-mono)' }}>TITLE</label>
              <input
                value={editTitle} onChange={e => setEditTitle(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', background: 'rgba(7,11,18,0.6)', border: '1px solid rgba(100,140,200,0.15)', borderRadius: 6, color: '#e2e8f0', fontSize: 13, outline: 'none', boxSizing: 'border-box' }}
              />
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', fontSize: 9, fontWeight: 700, color: '#3d4e64', letterSpacing: '0.1em', marginBottom: 5, fontFamily: 'var(--font-mono)' }}>STATUS</label>
                <select value={editStatus} onChange={e => setEditStatus(e.target.value as Task['status'])}
                  style={{ width: '100%', padding: '7px 8px', background: 'rgba(7,11,18,0.6)', border: '1px solid rgba(100,140,200,0.15)', borderRadius: 6, color: '#94a3b8', fontSize: 11, outline: 'none', fontFamily: 'var(--font-mono)' }}>
                  <option value="todo">Planned</option>
                  <option value="in_progress">In Progress</option>
                  <option value="done">Complete</option>
                </select>
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', fontSize: 9, fontWeight: 700, color: '#3d4e64', letterSpacing: '0.1em', marginBottom: 5, fontFamily: 'var(--font-mono)' }}>PRIORITY</label>
                <select value={editPriority} onChange={e => setEditPriority(e.target.value as Task['priority'])}
                  style={{ width: '100%', padding: '7px 8px', background: 'rgba(7,11,18,0.6)', border: '1px solid rgba(100,140,200,0.15)', borderRadius: 6, color: '#94a3b8', fontSize: 11, outline: 'none', fontFamily: 'var(--font-mono)' }}>
                  <option value="high">Critical</option>
                  <option value="medium">Standard</option>
                  <option value="low">Routine</option>
                </select>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', fontSize: 9, fontWeight: 700, color: '#3d4e64', letterSpacing: '0.1em', marginBottom: 5, fontFamily: 'var(--font-mono)' }}>DEADLINE</label>
                <input type="date" value={editDeadline} onChange={e => setEditDeadline(e.target.value)}
                  style={{ width: '100%', padding: '7px 8px', background: 'rgba(7,11,18,0.6)', border: '1px solid rgba(100,140,200,0.15)', borderRadius: 6, color: '#94a3b8', fontSize: 11, outline: 'none', boxSizing: 'border-box' }} />
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', fontSize: 9, fontWeight: 700, color: '#3d4e64', letterSpacing: '0.1em', marginBottom: 5, fontFamily: 'var(--font-mono)' }}>RESEARCHER</label>
                <select value={editAssigneeId} onChange={e => setEditAssigneeId(e.target.value)}
                  style={{ width: '100%', padding: '7px 8px', background: 'rgba(7,11,18,0.6)', border: '1px solid rgba(100,140,200,0.15)', borderRadius: 6, color: '#94a3b8', fontSize: 11, outline: 'none', fontFamily: 'var(--font-mono)' }}>
                  <option value="">Unassigned</option>
                  {members.map(m => <option key={m.user_id} value={m.user_id}>{m.username}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 9, fontWeight: 700, color: '#3d4e64', letterSpacing: '0.1em', marginBottom: 5, fontFamily: 'var(--font-mono)' }}>NOTES / PROTOCOL</label>
              <textarea
                value={editDescription} onChange={e => setEditDescription(e.target.value)}
                rows={4}
                style={{ width: '100%', padding: '8px 10px', background: 'rgba(7,11,18,0.6)', border: '1px solid rgba(100,140,200,0.15)', borderRadius: 6, color: '#e2e8f0', fontSize: 12, outline: 'none', boxSizing: 'border-box', resize: 'vertical', lineHeight: 1.55 }}
              />
            </div>

            <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
              <button onClick={handleSave} disabled={updateTask.isPending} style={{
                flex: 1, padding: '9px', cursor: 'pointer',
                background: 'rgba(34,211,238,0.12)', border: '1px solid rgba(34,211,238,0.28)',
                borderRadius: 7, color: '#22d3ee', fontSize: 10, fontWeight: 700,
                letterSpacing: '0.08em', fontFamily: 'var(--font-mono)',
                opacity: updateTask.isPending ? 0.6 : 1,
              }}>{updateTask.isPending ? 'SAVING…' : 'SAVE'}</button>
              <button onClick={() => setIsEditing(false)} style={{
                padding: '9px 14px', cursor: 'pointer',
                background: 'rgba(100,140,200,0.07)', border: '1px solid rgba(100,140,200,0.14)',
                borderRadius: 7, color: '#475569', fontSize: 10, fontFamily: 'var(--font-mono)',
              }}>CANCEL</button>
            </div>

            <div style={{ height: 1, background: 'rgba(100,140,200,0.07)' }} />

            <button
              onClick={handleDeleteClick}
              disabled={deleteTask.isPending}
              style={{
                padding: '8px', cursor: 'pointer',
                background: deleteConfirm ? 'rgba(244,63,94,0.18)' : 'rgba(244,63,94,0.07)',
                border: `1px solid rgba(244,63,94,${deleteConfirm ? '0.45' : '0.2'})`,
                borderRadius: 7, color: '#f43f5e',
                fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
                fontFamily: 'var(--font-mono)', transition: 'all 0.15s',
              }}
            >
              {deleteConfirm ? 'CONFIRM DELETE?' : 'DELETE TASK'}
            </button>
          </div>
        )}

        {/* Linked session */}
        {task.session_id && (
          <div style={{ background: 'rgba(34,211,238,0.04)', border: '1px solid rgba(34,211,238,0.14)', borderRadius: 8, padding: '12px 14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 9 }}>
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#22d3ee', boxShadow: '0 0 5px #22d3ee' }} />
              <span style={{ fontSize: 9, fontWeight: 700, color: '#22d3ee', letterSpacing: '0.12em', fontFamily: 'var(--font-mono)' }}>LINKED SESSION</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <code style={{ flex: 1, fontSize: 11, color: '#94a3b8', fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {task.session_id}
              </code>
              <button
                onClick={() => { navigator.clipboard.writeText(task.session_id!); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
                style={{
                  flexShrink: 0, padding: '3px 10px', fontSize: 10, cursor: 'pointer',
                  background: copied ? 'rgba(16,185,129,0.12)' : 'rgba(34,211,238,0.08)',
                  border: `1px solid ${copied ? 'rgba(16,185,129,0.28)' : 'rgba(34,211,238,0.22)'}`,
                  borderRadius: 5, color: copied ? '#10b981' : '#22d3ee',
                  fontFamily: 'var(--font-mono)', transition: 'all 0.2s',
                }}
              >{copied ? '✓ Copied' : 'Copy'}</button>
            </div>
            <p style={{ margin: '7px 0 0', fontSize: 10, color: '#3d4e64', fontFamily: 'var(--font-mono)' }}>
              EvoSci --resume {task.session_id}
            </p>
          </div>
        )}

        {/* Comments */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 9, fontWeight: 700, color: '#3d4e64', letterSpacing: '0.12em', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Lab Notes</span>
            <div style={{ flex: 1, height: 1, background: 'rgba(100,140,200,0.07)' }} />
            <span style={{ fontSize: 9, color: '#3d4e64', background: 'rgba(100,140,200,0.07)', border: '1px solid rgba(100,140,200,0.1)', borderRadius: 9, padding: '1px 7px', fontFamily: 'var(--font-mono)' }}>{comments.length}</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            {comments.map(c => (
              <div key={c.id} style={{ background: 'rgba(17,30,53,0.55)', border: '1px solid rgba(100,140,200,0.08)', borderRadius: 7, padding: '10px 12px', animation: 'fadeInUp 0.18s ease' }}>
                <p style={{ margin: '0 0 5px', fontSize: 13, color: '#cbd5e1', lineHeight: 1.55 }}>{c.body}</p>
                <p style={{ margin: 0, fontSize: 9, color: '#3d4e64', fontFamily: 'var(--font-mono)' }}>{c.created_at.slice(0, 10)}</p>
              </div>
            ))}
            {comments.length === 0 && (
              <p style={{ color: '#334155', fontSize: 12, fontStyle: 'italic', padding: '4px 0' }}>No lab notes yet.</p>
            )}
          </div>

          <form onSubmit={e => { e.preventDefault(); addComment.mutate(commentBody) }} style={{ display: 'flex', gap: 8, marginTop: 'auto' }}>
            <input
              value={commentBody} onChange={e => setCommentBody(e.target.value)}
              placeholder="Add a lab note…" required
              style={{ flex: 1, padding: '9px 12px', background: 'rgba(7,11,18,0.6)', border: '1px solid rgba(100,140,200,0.12)', borderRadius: 7, color: '#e2e8f0', fontSize: 12, outline: 'none', transition: 'border-color 0.14s' }}
              onFocus={e => { e.currentTarget.style.borderColor = 'rgba(34,211,238,0.3)' }}
              onBlur={e => { e.currentTarget.style.borderColor = 'rgba(100,140,200,0.12)' }}
            />
            <button type="submit" disabled={addComment.isPending} style={{
              padding: '9px 16px', fontSize: 11, cursor: 'pointer',
              background: 'rgba(34,211,238,0.1)', border: '1px solid rgba(34,211,238,0.25)',
              borderRadius: 7, color: '#22d3ee', fontWeight: 700, letterSpacing: '0.05em',
              transition: 'background 0.14s', fontFamily: 'var(--font-mono)',
            }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(34,211,238,0.2)' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'rgba(34,211,238,0.1)' }}
            >POST</button>
          </form>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify the build**

```bash
cd EvoScientist/pm/frontend && npm run build
```

Expected: `✓ built in ...ms` — no TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add EvoScientist/pm/frontend/src/pages/TaskDetail.tsx
git commit -m "feat(pm): add edit mode, assignee, delete, and overdue to TaskDetail"
```

---

## Task 7: Run all frontend tests and final build

**Files:** No changes — verification only.

- [ ] **Step 1: Run full test suite**

```bash
cd EvoScientist/pm/frontend && npm test -- --run
```

Expected: All tests pass. You should see:
- `hooks/__tests__/useTaskFilters.test.ts` — 9 passed
- `components/__tests__/FilterToolbar.test.tsx` — 8 passed
- `components/__tests__/CardEditPopover.test.tsx` — 5 passed

If any test fails, read the error carefully and fix the implementation (not the tests).

- [ ] **Step 2: Final production build**

```bash
cd EvoScientist/pm/frontend && npm run build
```

Expected:
```
✓ N modules transformed.
dist/index.html           ~0.4 kB
dist/assets/index-*.css   ~1.2 kB
dist/assets/index-*.js    ~280 kB (larger than before due to @dnd-kit)
✓ built in ...ms
```

- [ ] **Step 3: Stage and commit dist + any remaining files**

```bash
git add EvoScientist/pm/frontend/dist/
git commit -m "chore(pm): rebuild frontend with DnD and board UX features"
```

- [ ] **Step 4: Run Python tests to confirm backend is untouched**

```bash
cd /path/to/EvoScientist && uv run pytest tests/pm/ -v --timeout=30
```

Expected: All 51 tests pass (no backend changes were made).
