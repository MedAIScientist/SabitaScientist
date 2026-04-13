# Bulk Task Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users select multiple Board task cards with checkboxes and apply a status or phase change to all of them at once via a floating bulk action bar.

**Architecture:** Selection state (`selectedIds: Set<string>`) lives in `Board.tsx`. `DraggableCard` gains a checkbox (visible on hover or when selected) that toggles selection without opening the drawer. A new `BulkActionBar` component renders fixed at the board bottom when selection is non-empty. Selecting a status/phase value fires parallel `api.updateTask` calls then clears selection. Props thread through `DroppableColumn` and `PhaseSwimLane` to reach individual cards.

**Tech Stack:** React 18, TypeScript, TanStack Query v5, Vitest + @testing-library/react, jsdom.

---

## File Map

**New files:**
- `EvoScientist/pm/frontend/src/components/board/BulkActionBar.tsx` — floating toolbar
- `EvoScientist/pm/frontend/src/components/board/__tests__/BulkActionBar.test.tsx`
- `EvoScientist/pm/frontend/src/components/board/__tests__/DraggableCard.test.tsx`

**Modified files:**
- `EvoScientist/pm/frontend/src/components/board/DraggableCard.tsx` — add `isSelected` + `onToggleSelect` props + checkbox
- `EvoScientist/pm/frontend/src/components/board/DroppableColumn.tsx` — thread new props to `DraggableCard`
- `EvoScientist/pm/frontend/src/components/board/PhaseSwimLane.tsx` — thread new props to `DroppableColumn`
- `EvoScientist/pm/frontend/src/pages/Board.tsx` — `selectedIds` state, `toggleSelect`, `applyBulkUpdate`, render `BulkActionBar`
- `EvoScientist/pm/frontend/src/pages/__tests__/Board.test.tsx` — 2 new tests

---

## Task 1: Create `BulkActionBar.tsx` with tests

**Files:**
- Create: `EvoScientist/pm/frontend/src/components/board/BulkActionBar.tsx`
- Create: `EvoScientist/pm/frontend/src/components/board/__tests__/BulkActionBar.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `EvoScientist/pm/frontend/src/components/board/__tests__/BulkActionBar.test.tsx`:

```typescript
// EvoScientist/pm/frontend/src/components/board/__tests__/BulkActionBar.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi } from 'vitest'
import { BulkActionBar } from '../BulkActionBar'

const PHASES = [
  { id: 'ph1', name: 'Phase 1' },
  { id: 'ph2', name: 'Phase 2' },
]

describe('BulkActionBar', () => {
  test('renders selected count', () => {
    render(
      <BulkActionBar
        count={3}
        phases={PHASES}
        onStatusChange={vi.fn()}
        onPhaseChange={vi.fn()}
        onClear={vi.fn()}
      />
    )
    expect(screen.getByText(/3 selected/i)).toBeInTheDocument()
  })

  test('status dropdown calls onStatusChange with chosen value', () => {
    const onStatusChange = vi.fn()
    render(
      <BulkActionBar
        count={2}
        phases={PHASES}
        onStatusChange={onStatusChange}
        onPhaseChange={vi.fn()}
        onClear={vi.fn()}
      />
    )
    fireEvent.change(screen.getByTestId('bulk-status-select'), {
      target: { value: 'done' },
    })
    expect(onStatusChange).toHaveBeenCalledWith('done')
  })

  test('phase dropdown calls onPhaseChange with phase id', () => {
    const onPhaseChange = vi.fn()
    render(
      <BulkActionBar
        count={2}
        phases={PHASES}
        onStatusChange={vi.fn()}
        onPhaseChange={onPhaseChange}
        onClear={vi.fn()}
      />
    )
    fireEvent.change(screen.getByTestId('bulk-phase-select'), {
      target: { value: 'ph1' },
    })
    expect(onPhaseChange).toHaveBeenCalledWith('ph1')
  })

  test('phase dropdown calls onPhaseChange with null for empty value', () => {
    const onPhaseChange = vi.fn()
    render(
      <BulkActionBar
        count={2}
        phases={PHASES}
        onStatusChange={vi.fn()}
        onPhaseChange={onPhaseChange}
        onClear={vi.fn()}
      />
    )
    fireEvent.change(screen.getByTestId('bulk-phase-select'), {
      target: { value: '' },
    })
    expect(onPhaseChange).toHaveBeenCalledWith(null)
  })

  test('clear button calls onClear', () => {
    const onClear = vi.fn()
    render(
      <BulkActionBar
        count={2}
        phases={PHASES}
        onStatusChange={vi.fn()}
        onPhaseChange={vi.fn()}
        onClear={onClear}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /clear/i }))
    expect(onClear).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/components/board/__tests__/BulkActionBar.test.tsx
```

Expected: FAIL — `Cannot find module '../BulkActionBar'`

- [ ] **Step 3: Create `BulkActionBar.tsx`**

Create `EvoScientist/pm/frontend/src/components/board/BulkActionBar.tsx`:

```typescript
// EvoScientist/pm/frontend/src/components/board/BulkActionBar.tsx
import React from 'react'
import type { Task } from '../../api'

interface Phase {
  id: string
  name: string
}

interface Props {
  count: number
  phases: Phase[]
  onStatusChange: (status: Task['status']) => void
  onPhaseChange: (phaseId: string | null) => void
  onClear: () => void
}

const selectStyle: React.CSSProperties = {
  padding: '5px 10px',
  background: 'var(--surface-input)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  color: 'var(--text)',
  fontSize: 20,
  cursor: 'pointer',
  fontFamily: 'var(--font-mono)',
  outline: 'none',
}

export function BulkActionBar({ count, phases, onStatusChange, onPhaseChange, onClear }: Props) {
  return (
    <div style={{
      position: 'fixed',
      bottom: 24,
      left: '50%',
      transform: 'translateX(-50%)',
      zIndex: 200,
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      background: 'var(--surface)',
      border: '1px solid rgba(255,128,21,0.35)',
      borderRadius: 10,
      padding: '10px 16px',
      boxShadow: '0 8px 32px rgba(0,0,0,0.35), 0 0 0 1px rgba(255,128,21,0.12)',
      backdropFilter: 'blur(12px)',
    }}>
      <span style={{
        fontSize: 20,
        fontWeight: 700,
        color: '#ff8015',
        fontFamily: 'var(--font-mono)',
        letterSpacing: '0.05em',
        whiteSpace: 'nowrap',
      }}>
        {count} selected
      </span>

      <div style={{ width: 1, height: 20, background: 'var(--border)', flexShrink: 0 }} />

      <select
        data-testid="bulk-status-select"
        defaultValue=""
        onChange={e => {
          if (e.target.value) {
            onStatusChange(e.target.value as Task['status'])
            e.target.value = ''
          }
        }}
        style={selectStyle}
      >
        <option value="" disabled>Set status…</option>
        <option value="todo">PLANNED</option>
        <option value="in_progress">IN PROGRESS</option>
        <option value="done">COMPLETE</option>
      </select>

      <select
        data-testid="bulk-phase-select"
        defaultValue=""
        onChange={e => {
          const val = e.target.value
          onPhaseChange(val === '' ? null : val)
          e.target.value = ''
        }}
        style={selectStyle}
      >
        <option value="" disabled>Set phase…</option>
        <option value="">No phase</option>
        {phases.map(p => (
          <option key={p.id} value={p.id}>{p.name}</option>
        ))}
      </select>

      <button
        onClick={onClear}
        style={{
          padding: '5px 10px',
          background: 'none',
          border: '1px solid var(--border)',
          borderRadius: 6,
          color: 'var(--text-dim)',
          fontSize: 20,
          cursor: 'pointer',
          fontFamily: 'var(--font-mono)',
          transition: 'border-color 0.14s, color 0.14s',
        }}
        onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(244,63,94,0.4)'; e.currentTarget.style.color = '#f43f5e' }}
        onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-dim)' }}
      >✕ Clear</button>
    </div>
  )
}
```

- [ ] **Step 4: Run tests — confirm all 5 PASS**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/components/board/__tests__/BulkActionBar.test.tsx
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/frontend/src/components/board/BulkActionBar.tsx \
        EvoScientist/pm/frontend/src/components/board/__tests__/BulkActionBar.test.tsx
git commit -m "feat(pm): add BulkActionBar component for board bulk task operations"
```

---

## Task 2: Add checkbox to `DraggableCard` with tests

**Files:**
- Modify: `EvoScientist/pm/frontend/src/components/board/DraggableCard.tsx`
- Create: `EvoScientist/pm/frontend/src/components/board/__tests__/DraggableCard.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `EvoScientist/pm/frontend/src/components/board/__tests__/DraggableCard.test.tsx`:

```typescript
// EvoScientist/pm/frontend/src/components/board/__tests__/DraggableCard.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi } from 'vitest'

vi.mock('@dnd-kit/core', () => ({
  useDraggable: () => ({ attributes: {}, listeners: {}, setNodeRef: () => {}, transform: null }),
}))
vi.mock('@dnd-kit/utilities', () => ({
  CSS: { Transform: { toString: () => '' } },
}))

import { DraggableCard, ColumnDef } from '../DraggableCard'
import type { Task } from '../../../api'

const COL: ColumnDef = {
  key: 'todo',
  label: 'PLANNED',
  accent: '#ff8015',
  glow: '255,128,21',
}

const TASK: Task = {
  id: 'task-1', project_id: 'proj-1',
  title: 'Design primer sequences',
  description: null, assignee_id: null,
  status: 'todo', priority: 'high',
  deadline: null, session_id: null,
  created_by: 'u1', created_at: '2026-01-01', updated_at: '2026-01-01',
}

describe('DraggableCard checkbox', () => {
  test('checkbox visible when isSelected=true', () => {
    render(
      <DraggableCard
        task={TASK} col={COL} idx={0} activeTaskId={null}
        onCardClick={vi.fn()} onEditClick={vi.fn()} members={[]}
        isSelected={true} onToggleSelect={vi.fn()}
      />
    )
    expect(screen.getByRole('checkbox')).toBeInTheDocument()
    expect(screen.getByRole('checkbox')).toBeChecked()
  })

  test('checkbox visible on hover', () => {
    const { container } = render(
      <DraggableCard
        task={TASK} col={COL} idx={0} activeTaskId={null}
        onCardClick={vi.fn()} onEditClick={vi.fn()} members={[]}
        isSelected={false} onToggleSelect={vi.fn()}
      />
    )
    const card = container.querySelector('[data-card="true"]') as HTMLElement
    // Before hover: no checkbox
    expect(screen.queryByRole('checkbox')).toBeNull()
    // After hover: checkbox appears
    fireEvent.mouseEnter(card)
    expect(screen.getByRole('checkbox')).toBeInTheDocument()
  })

  test('clicking checkbox calls onToggleSelect with task id', () => {
    const onToggleSelect = vi.fn()
    render(
      <DraggableCard
        task={TASK} col={COL} idx={0} activeTaskId={null}
        onCardClick={vi.fn()} onEditClick={vi.fn()} members={[]}
        isSelected={true} onToggleSelect={onToggleSelect}
      />
    )
    fireEvent.click(screen.getByRole('checkbox'))
    expect(onToggleSelect).toHaveBeenCalledWith('task-1')
  })

  test('clicking checkbox does NOT call onCardClick', () => {
    const onCardClick = vi.fn()
    render(
      <DraggableCard
        task={TASK} col={COL} idx={0} activeTaskId={null}
        onCardClick={onCardClick} onEditClick={vi.fn()} members={[]}
        isSelected={true} onToggleSelect={vi.fn()}
      />
    )
    fireEvent.click(screen.getByRole('checkbox'))
    expect(onCardClick).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/components/board/__tests__/DraggableCard.test.tsx
```

Expected: FAIL — missing `isSelected`/`onToggleSelect` props

- [ ] **Step 3: Modify `DraggableCard.tsx`**

Open `EvoScientist/pm/frontend/src/components/board/DraggableCard.tsx`.

**Change 1:** Update `DraggableCardProps` interface — add two new props after `members`:

```typescript
export interface DraggableCardProps {
  task: Task
  col: ColumnDef
  idx: number
  activeTaskId: string | null
  onCardClick: (task: Task) => void
  onEditClick: (task: Task, rect: DOMRect) => void
  members: { user_id: string; username: string }[]
  isSelected: boolean
  onToggleSelect: (taskId: string) => void
}
```

**Change 2:** Update the function signature to destructure the new props:

```typescript
export function DraggableCard({
  task, col, idx, activeTaskId, onCardClick, onEditClick, members,
  isSelected, onToggleSelect,
}: DraggableCardProps) {
```

**Change 3:** Update `cardStyle` to add orange border when selected. Replace the existing `cardStyle` definition:

```typescript
  const cardStyle: React.CSSProperties = {
    background: 'var(--surface-card)',
    border: isSelected
      ? '1px solid rgba(255,128,21,0.45)'
      : '1px solid var(--border-subtle)',
    borderLeft: overdue ? '3px solid #f43f5e' : undefined,
    borderRadius: 7,
    padding: '11px 13px',
    cursor: 'pointer',
    transition: 'transform 0.14s, border-color 0.14s, box-shadow 0.14s',
    animation: 'fadeInUp 0.22s ease both',
    animationDelay: `${idx * 0.035}s`,
    opacity: isDragging ? 0.35 : 1,
    position: 'relative',
    transform: CSS.Transform.toString(transform) ?? undefined,
  }
```

**Change 4:** Add the checkbox just before the existing edit icon button (inside the returned JSX, as the first child after the outer `<div>`). Insert this block right before the `{/* Edit icon (shown on hover) */}` comment:

```tsx
      {/* Selection checkbox (shown on hover or when selected) */}
      {(isHovered || isSelected) && (
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => {}}
          onPointerDown={e => e.stopPropagation()}
          onClick={e => {
            e.stopPropagation()
            onToggleSelect(task.id)
          }}
          style={{
            position: 'absolute',
            top: 8,
            left: 8,
            width: 14,
            height: 14,
            cursor: 'pointer',
            accentColor: '#ff8015',
            zIndex: 3,
          }}
        />
      )}
```

- [ ] **Step 4: Run tests — confirm 4 PASS**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/components/board/__tests__/DraggableCard.test.tsx
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/frontend/src/components/board/DraggableCard.tsx \
        EvoScientist/pm/frontend/src/components/board/__tests__/DraggableCard.test.tsx
git commit -m "feat(pm): add selection checkbox to DraggableCard"
```

---

## Task 3: Thread selection props through `DroppableColumn` and `PhaseSwimLane`

**Files:**
- Modify: `EvoScientist/pm/frontend/src/components/board/DroppableColumn.tsx`
- Modify: `EvoScientist/pm/frontend/src/components/board/PhaseSwimLane.tsx`

No new tests for this task — these are pure prop pass-throughs. The Board integration test in Task 4 will verify end-to-end.

- [ ] **Step 1: Update `DroppableColumn.tsx`**

Open `EvoScientist/pm/frontend/src/components/board/DroppableColumn.tsx`.

**Change 1:** Add two props to `DroppableColumnProps`:

```typescript
export interface DroppableColumnProps {
  col: ColumnDef
  colTasks: Task[]
  colExps: Experiment[]
  isDropTarget: boolean
  activeTaskId: string | null
  addingToCol: Task['status'] | null
  newTaskTitle: string
  onNewTaskTitleChange: (v: string) => void
  onAddStart: (status: Task['status']) => void
  onAddCancel: () => void
  onAddSubmit: (title: string) => void
  onCardClick: (task: Task) => void
  onEditClick: (task: Task, rect: DOMRect) => void
  onExpClick: (exp: Experiment) => void
  members: { user_id: string; username: string }[]
  selectedIds: Set<string>
  onToggleSelect: (taskId: string) => void
}
```

**Change 2:** Destructure the new props in `DroppableColumn` function:

```typescript
export function DroppableColumn({
  col, colTasks, colExps, isDropTarget, activeTaskId,
  addingToCol, newTaskTitle, onNewTaskTitleChange,
  onAddStart, onAddCancel, onAddSubmit,
  onCardClick, onEditClick, onExpClick, members,
  selectedIds, onToggleSelect,
}: DroppableColumnProps) {
```

**Change 3:** Pass `isSelected` and `onToggleSelect` to each `DraggableCard`. Find the `{colTasks.map(...)}` block and update it:

```tsx
        {colTasks.map((task, idx) => (
          <DraggableCard
            key={task.id}
            task={task}
            col={col}
            idx={colExps.length + idx}
            activeTaskId={activeTaskId}
            onCardClick={onCardClick}
            onEditClick={onEditClick}
            members={members}
            isSelected={selectedIds.has(task.id)}
            onToggleSelect={onToggleSelect}
          />
        ))}
```

- [ ] **Step 2: Update `PhaseSwimLane.tsx`**

Open `EvoScientist/pm/frontend/src/components/board/PhaseSwimLane.tsx`.

**Change 1:** Add two props to `PhaseSwimLaneProps`:

```typescript
export interface PhaseSwimLaneProps {
  phase: ProjectPhase | null
  tasks: Task[]
  experiments: Experiment[]
  overColumnId: string | null
  activeTaskId: string | null
  addingToCol: Task['status'] | null
  newTaskTitle: string
  onNewTaskTitleChange: (v: string) => void
  onAddStart: (status: Task['status']) => void
  onAddCancel: () => void
  onAddSubmit: (col: Task['status']) => (title: string) => void
  onCardClick: (task: Task) => void
  onEditClick: (task: Task, rect: DOMRect) => void
  onExpClick: (exp: Experiment) => void
  members: { user_id: string; username: string }[]
  selectedIds: Set<string>
  onToggleSelect: (taskId: string) => void
}
```

**Change 2:** Destructure new props in `PhaseSwimLane` function. Find the function definition and add the two new props to its destructured params:

```typescript
export function PhaseSwimLane({
  phase, tasks, experiments, overColumnId, activeTaskId,
  addingToCol, newTaskTitle, onNewTaskTitleChange,
  onAddStart, onAddCancel, onAddSubmit,
  onCardClick, onEditClick, onExpClick, members,
  selectedIds, onToggleSelect,
}: PhaseSwimLaneProps) {
```

**Change 3:** Pass `selectedIds` and `onToggleSelect` to each `DroppableColumn` inside `PhaseSwimLane`. Find every `<DroppableColumn` usage in the file and add the two props:

```tsx
              <DroppableColumn
                key={col.key}
                col={col}
                colTasks={colTasks}
                colExps={colExps}
                isDropTarget={overColumnId === col.key}
                activeTaskId={activeTaskId}
                addingToCol={addingToCol}
                newTaskTitle={newTaskTitle}
                onNewTaskTitleChange={onNewTaskTitleChange}
                onAddStart={onAddStart}
                onAddCancel={onAddCancel}
                onAddSubmit={onAddSubmit(col.key)}
                onCardClick={onCardClick}
                onEditClick={onEditClick}
                onExpClick={onExpClick}
                members={members}
                selectedIds={selectedIds}
                onToggleSelect={onToggleSelect}
              />
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd EvoScientist/pm/frontend && npx tsc --noEmit
```

Expected: No errors (or only pre-existing errors unrelated to these changes).

- [ ] **Step 4: Commit**

```bash
git add EvoScientist/pm/frontend/src/components/board/DroppableColumn.tsx \
        EvoScientist/pm/frontend/src/components/board/PhaseSwimLane.tsx
git commit -m "refactor(pm): thread selectedIds/onToggleSelect through DroppableColumn and PhaseSwimLane"
```

---

## Task 4: Wire `Board.tsx` and add Board integration tests

**Files:**
- Modify: `EvoScientist/pm/frontend/src/pages/Board.tsx`
- Modify: `EvoScientist/pm/frontend/src/pages/__tests__/Board.test.tsx`

- [ ] **Step 1: Add 2 new failing tests to `Board.test.tsx`**

Open `EvoScientist/pm/frontend/src/pages/__tests__/Board.test.tsx`. Before the closing `})` of the `describe('Board', ...)` block, add:

```typescript
  test('selecting a card renders BulkActionBar with count 1', () => {
    renderBoard()
    const cardTitle = screen.getByText('Design primer sequences')
    const card = cardTitle.closest('[data-card="true"]') as HTMLElement
    expect(card).not.toBeNull()
    fireEvent.mouseEnter(card)
    const checkbox = card.querySelector('input[type="checkbox"]') as HTMLElement
    expect(checkbox).not.toBeNull()
    fireEvent.click(checkbox)
    expect(screen.getByText(/1 selected/i)).toBeInTheDocument()
  })

  test('clearing selection hides BulkActionBar', () => {
    renderBoard()
    const cardTitle = screen.getByText('Design primer sequences')
    const card = cardTitle.closest('[data-card="true"]') as HTMLElement
    fireEvent.mouseEnter(card)
    const checkbox = card.querySelector('input[type="checkbox"]') as HTMLElement
    fireEvent.click(checkbox)
    expect(screen.getByText(/1 selected/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /clear/i }))
    expect(screen.queryByText(/1 selected/i)).toBeNull()
  })
```

- [ ] **Step 2: Run new tests — confirm FAIL**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/pages/__tests__/Board.test.tsx
```

Expected: The 2 new tests fail (BulkActionBar not yet wired into Board).

- [ ] **Step 3: Update `Board.tsx`**

Open `EvoScientist/pm/frontend/src/pages/Board.tsx`.

**Change 1:** Add `BulkActionBar` import at the top with other board component imports:

```typescript
import { BulkActionBar } from '../components/board/BulkActionBar'
```

**Change 2:** Add `selectedIds` state after the existing state declarations (e.g., after `settingsPanelOpen`):

```typescript
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
```

**Change 3:** Add `toggleSelect` callback after the existing callbacks (e.g., after `handleEditClick`):

```typescript
  const toggleSelect = useCallback((taskId: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      next.has(taskId) ? next.delete(taskId) : next.add(taskId)
      return next
    })
  }, [])
```

**Change 4:** Add `applyBulkUpdate` handler after `toggleSelect`:

```typescript
  const applyBulkUpdate = useCallback(async (updates: Partial<Task>) => {
    await Promise.all(
      [...selectedIds].map(id => api.updateTask(projectId!, id, updates))
    )
    queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
    setSelectedIds(new Set())
  }, [selectedIds, projectId, queryClient])
```

**Change 5:** Pass `selectedIds` and `onToggleSelect={toggleSelect}` to every `<DroppableColumn>` (flat kanban branch) and `<PhaseSwimLane>` (swimlane branch).

For the flat kanban (`phases.length === 0`) branch, update each `<DroppableColumn>`:

```tsx
                <DroppableColumn
                  key={col.key}
                  col={col}
                  colTasks={colTasks}
                  colExps={colExps}
                  isDropTarget={overColumnId === col.key}
                  activeTaskId={activeTaskId}
                  addingToCol={addingToCol}
                  newTaskTitle={newTaskTitle}
                  onNewTaskTitleChange={setNewTaskTitle}
                  onAddStart={setAddingToCol}
                  onAddCancel={handleAddCancel}
                  onAddSubmit={handleAddSubmit(col.key)}
                  onCardClick={handleCardClick}
                  onEditClick={handleEditClick}
                  onExpClick={handleExpClick}
                  members={project?.members ?? []}
                  selectedIds={selectedIds}
                  onToggleSelect={toggleSelect}
                />
```

For the swimlane branch, update each `<PhaseSwimLane>` (both the per-phase and the unassigned ones):

```tsx
                <PhaseSwimLane
                  key={phase.id}
                  phase={phase}
                  tasks={laneTasks}
                  experiments={laneExps}
                  overColumnId={overColumnId}
                  activeTaskId={activeTaskId}
                  addingToCol={addingToCol}
                  newTaskTitle={newTaskTitle}
                  onNewTaskTitleChange={setNewTaskTitle}
                  onAddStart={setAddingToCol}
                  onAddCancel={handleAddCancel}
                  onAddSubmit={handleAddSubmit}
                  onCardClick={handleCardClick}
                  onEditClick={handleEditClick}
                  onExpClick={handleExpClick}
                  members={project?.members ?? []}
                  selectedIds={selectedIds}
                  onToggleSelect={toggleSelect}
                />
```

(Apply the same `selectedIds` + `onToggleSelect` addition to the unassigned `<PhaseSwimLane key="unassigned" ...>` as well.)

**Change 6:** Render `BulkActionBar` conditionally. Add before the closing `</div>` of the outer Board container (after the `settingsPanelOpen` block):

```tsx
      {selectedIds.size > 0 && (
        <BulkActionBar
          count={selectedIds.size}
          phases={phases}
          onStatusChange={status => applyBulkUpdate({ status })}
          onPhaseChange={phaseId => applyBulkUpdate({ phase_id: phaseId })}
          onClear={() => setSelectedIds(new Set())}
        />
      )}
```

- [ ] **Step 4: Run new Board tests — confirm 2 PASS**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/pages/__tests__/Board.test.tsx
```

Expected: All Board tests pass including the 2 new ones.

- [ ] **Step 5: Run full frontend suite**

```bash
cd EvoScientist/pm/frontend && npx vitest run
```

Expected: All tests pass (116+ passing, only pre-existing `ProjectSettingsPanel` failures acceptable).

- [ ] **Step 6: Commit**

```bash
git add EvoScientist/pm/frontend/src/pages/Board.tsx \
        EvoScientist/pm/frontend/src/pages/__tests__/Board.test.tsx
git commit -m "feat(pm): wire bulk task selection and BulkActionBar into Board"
```

---

## Task 5: Final validation

- [ ] **Step 1: Run backend PM tests**

```bash
uv run pytest tests/pm/ --timeout=30 -q
```

Expected: 164 passed, 0 failed (no backend was touched).

- [ ] **Step 2: Run full frontend suite**

```bash
cd EvoScientist/pm/frontend && npx vitest run
```

Expected: All new tests pass, no unexpected regressions.

- [ ] **Step 3: Verify TypeScript**

```bash
cd EvoScientist/pm/frontend && npx tsc --noEmit
```

Expected: No new errors introduced.
