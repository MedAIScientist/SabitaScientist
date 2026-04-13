# TaskDetail Refactor & 4-Tab UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the 631-line `TaskDetail.tsx` into four focused tab-scoped components and redesign the drawer from a view/edit mode toggle to a `DETAILS | NOTES | AI RUNS | EDIT` four-tab layout.

**Architecture:** `TaskDetail.tsx` becomes a thin orchestrator owning all queries, mutations, and state. Four child components each own one tab's rendering — `TaskDetailView`, `LabNotesTab`, `TaskEditForm` (new), plus the existing `AiRunsTab` (unchanged). Shared style constants move to `components/task/taskStyles.ts`.

**Tech Stack:** React 18, TypeScript, TanStack Query v5, Vitest + @testing-library/react, jsdom.

---

## File Map

**New files:**
- `src/components/task/taskStyles.ts` — shared style constants and metadata maps
- `src/components/task/TaskDetailView.tsx` — DETAILS tab (badges, description, session card, dependencies)
- `src/components/task/LabNotesTab.tsx` — NOTES tab (comment list + add form)
- `src/components/task/TaskEditForm.tsx` — EDIT tab (6-field form + delete button)
- `src/components/__tests__/TaskDetailView.test.tsx`
- `src/components/__tests__/LabNotesTab.test.tsx`
- `src/components/__tests__/TaskEditForm.test.tsx`

**Modified files:**
- `src/pages/TaskDetail.tsx` — refactored to orchestrator (~200 lines), 4-tab layout
- `src/pages/__tests__/TaskDetail.test.tsx` — update mocks and tab assertions

**Unchanged files:**
- `src/components/AiRunsTab.tsx`
- `src/components/DependencyPicker.tsx`
- `src/components/DeadlinePicker.tsx`

---

## Task 1: Create `taskStyles.ts` — shared constants

**Files:**
- Create: `EvoScientist/pm/frontend/src/components/task/taskStyles.ts`

- [ ] **Step 1: Create the file**

```typescript
// EvoScientist/pm/frontend/src/components/task/taskStyles.ts

export const STATUS_META: Record<string, { color: string; bg: string; label: string }> = {
  todo:        { color: '#ff8015', bg: 'rgba(255,128,21,0.08)',  label: 'PLANNED'     },
  in_progress: { color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', label: 'IN PROGRESS' },
  done:        { color: '#10b981', bg: 'rgba(16,185,129,0.08)', label: 'COMPLETE'    },
}

export const PRIORITY_META: Record<string, { color: string; bg: string; label: string }> = {
  high:   { color: '#f43f5e', bg: 'rgba(244,63,94,0.1)',   label: 'CRITICAL' },
  medium: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  label: 'STANDARD' },
  low:    { color: '#22c55e', bg: 'rgba(34,197,94,0.1)',   label: 'ROUTINE'  },
}

export function isOverdue(deadline: string | null): boolean {
  return Boolean(deadline) && new Date(deadline!) < new Date()
}

export const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 11px',
  background: 'var(--surface-input)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  color: 'var(--text)',
  fontSize: 22,
  outline: 'none',
  boxSizing: 'border-box',
  fontFamily: 'inherit',
}

export const selectStyle: React.CSSProperties = {
  ...inputStyle,
  cursor: 'pointer',
}

export const labelStyle: React.CSSProperties = {
  fontSize: 15,
  fontWeight: 700,
  color: 'var(--text-dim)',
  letterSpacing: '0.12em',
  textTransform: 'uppercase' as const,
  fontFamily: 'var(--font-mono)',
  marginBottom: 5,
  display: 'block',
}
```

- [ ] **Step 2: Commit**

```bash
git add EvoScientist/pm/frontend/src/components/task/taskStyles.ts
git commit -m "refactor(pm): extract TaskDetail shared style constants to taskStyles.ts"
```

---

## Task 2: Create `LabNotesTab.tsx` with tests

**Files:**
- Create: `EvoScientist/pm/frontend/src/components/task/LabNotesTab.tsx`
- Create: `EvoScientist/pm/frontend/src/components/__tests__/LabNotesTab.test.tsx`

- [ ] **Step 1: Write the failing tests**

```typescript
// EvoScientist/pm/frontend/src/components/__tests__/LabNotesTab.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi } from 'vitest'
import { LabNotesTab } from '../task/LabNotesTab'

const COMMENTS = [
  { id: 'c1', body: 'Buffer pH confirmed at 7.4', created_at: '2026-03-01T10:00:00Z' },
  { id: 'c2', body: 'Gel shows expected bands', created_at: '2026-03-02T11:00:00Z' },
]

describe('LabNotesTab', () => {
  test('renders all comments', () => {
    render(
      <LabNotesTab
        comments={COMMENTS}
        commentBody=""
        setCommentBody={vi.fn()}
        onSubmit={vi.fn()}
        isPending={false}
      />
    )
    expect(screen.getByText('Buffer pH confirmed at 7.4')).toBeInTheDocument()
    expect(screen.getByText('Gel shows expected bands')).toBeInTheDocument()
  })

  test('renders empty state when no comments', () => {
    render(
      <LabNotesTab
        comments={[]}
        commentBody=""
        setCommentBody={vi.fn()}
        onSubmit={vi.fn()}
        isPending={false}
      />
    )
    expect(screen.getByText(/no lab notes yet/i)).toBeInTheDocument()
  })

  test('calls setCommentBody on input change', () => {
    const setCommentBody = vi.fn()
    render(
      <LabNotesTab
        comments={[]}
        commentBody=""
        setCommentBody={setCommentBody}
        onSubmit={vi.fn()}
        isPending={false}
      />
    )
    fireEvent.change(screen.getByPlaceholderText(/add a lab note/i), {
      target: { value: 'New observation' },
    })
    expect(setCommentBody).toHaveBeenCalledWith('New observation')
  })

  test('calls onSubmit on form submit', () => {
    const onSubmit = vi.fn()
    render(
      <LabNotesTab
        comments={[]}
        commentBody="test note"
        setCommentBody={vi.fn()}
        onSubmit={onSubmit}
        isPending={false}
      />
    )
    fireEvent.submit(screen.getByRole('form'))
    expect(onSubmit).toHaveBeenCalled()
  })

  test('POST button disabled while isPending', () => {
    render(
      <LabNotesTab
        comments={[]}
        commentBody=""
        setCommentBody={vi.fn()}
        onSubmit={vi.fn()}
        isPending={true}
      />
    )
    expect(screen.getByRole('button', { name: /POST/i })).toBeDisabled()
  })
})
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/components/__tests__/LabNotesTab.test.tsx
```

Expected: FAIL — `Cannot find module '../task/LabNotesTab'`

- [ ] **Step 3: Create `LabNotesTab.tsx`**

```typescript
// EvoScientist/pm/frontend/src/components/task/LabNotesTab.tsx
import React from 'react'

interface Comment {
  id: string
  body: string
  created_at: string
}

interface Props {
  comments: Comment[]
  commentBody: string
  setCommentBody: (v: string) => void
  onSubmit: () => void
  isPending: boolean
}

export function LabNotesTab({ comments, commentBody, setCommentBody, onSubmit, isPending }: Props) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{
          fontSize: 15, fontWeight: 700, color: 'var(--text-dim)',
          letterSpacing: '0.12em', textTransform: 'uppercase',
          fontFamily: 'var(--font-mono)',
        }}>Lab Notes</span>
        <div style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
        <span style={{
          fontSize: 15, color: 'var(--text-dim)',
          background: 'var(--border-subtle)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 9, padding: '1px 7px',
          fontFamily: 'var(--font-mono)',
        }}>{comments.length}</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        {comments.map((c) => (
          <div key={c.id} style={{
            background: 'var(--surface-comment)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 7, padding: '10px 12px',
            animation: 'fadeInUp 0.18s ease',
          }}>
            <p style={{ margin: '0 0 5px', fontSize: 22, color: 'var(--text)', lineHeight: 1.55 }}>{c.body}</p>
            <p style={{ margin: 0, fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
              {c.created_at.slice(0, 10)}
            </p>
          </div>
        ))}
        {comments.length === 0 && (
          <p style={{ color: 'var(--text-muted)', fontSize: 21, fontStyle: 'italic', padding: '4px 0' }}>
            No lab notes yet.
          </p>
        )}
      </div>

      <form
        aria-label="add-lab-note"
        onSubmit={(e) => { e.preventDefault(); onSubmit() }}
        style={{ display: 'flex', gap: 8, marginTop: 'auto' }}
      >
        <input
          value={commentBody}
          onChange={e => setCommentBody(e.target.value)}
          placeholder="Add a lab note…"
          required
          style={{
            flex: 1, padding: '9px 12px',
            background: 'var(--surface-input)',
            border: '1px solid var(--border)',
            borderRadius: 7, color: 'var(--text)',
            fontSize: 21, outline: 'none',
            transition: 'border-color 0.14s',
          }}
          onFocus={e => { e.currentTarget.style.borderColor = 'rgba(255,128,21,0.3)' }}
          onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
        />
        <button
          type="submit"
          disabled={isPending}
          style={{
            padding: '9px 16px', fontSize: 20, cursor: 'pointer',
            background: 'rgba(255,128,21,0.1)',
            border: '1px solid rgba(255,128,21,0.25)',
            borderRadius: 7, color: '#ff8015', fontWeight: 700,
            letterSpacing: '0.05em', transition: 'background 0.14s',
            fontFamily: 'var(--font-mono)',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.2)' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.1)' }}
        >POST</button>
      </form>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/components/__tests__/LabNotesTab.test.tsx
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/frontend/src/components/task/LabNotesTab.tsx \
        EvoScientist/pm/frontend/src/components/__tests__/LabNotesTab.test.tsx
git commit -m "feat(pm): add LabNotesTab component for task drawer NOTES tab"
```

---

## Task 3: Create `TaskDetailView.tsx` with tests

**Files:**
- Create: `EvoScientist/pm/frontend/src/components/task/TaskDetailView.tsx`
- Create: `EvoScientist/pm/frontend/src/components/__tests__/TaskDetailView.test.tsx`

- [ ] **Step 1: Write the failing tests**

```typescript
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/components/__tests__/TaskDetailView.test.tsx
```

Expected: FAIL — `Cannot find module '../task/TaskDetailView'`

- [ ] **Step 3: Create `TaskDetailView.tsx`**

```typescript
// EvoScientist/pm/frontend/src/components/task/TaskDetailView.tsx
import React from 'react'
import { DependencyPicker } from '../DependencyPicker'
import { STATUS_META, PRIORITY_META, isOverdue, labelStyle } from './taskStyles'
import type { Task, Member } from '../../api'

interface Props {
  task: Task & { blocked_by?: string[] }
  projectId: string
  members: Member[]
  token: string | null
  allTasks: { id: string; title: string }[]
  copied: boolean
  onCopySessionId: () => void
}

export function TaskDetailView({ task, projectId, members, token, allTasks, copied, onCopySessionId }: Props) {
  const status   = STATUS_META[task.status]   ?? STATUS_META.todo
  const priority = PRIORITY_META[task.priority] ?? PRIORITY_META.low
  const overdue  = isOverdue(task.deadline)

  const deadlineBadgeStyle: React.CSSProperties = overdue
    ? {
        padding: '3px 10px', borderRadius: 4,
        background: 'rgba(244,63,94,0.12)',
        border: '1px solid rgba(244,63,94,0.28)',
        color: '#f43f5e', fontSize: 15, fontWeight: 700,
        fontFamily: 'var(--font-mono)',
      }
    : {
        padding: '3px 10px', borderRadius: 4,
        background: 'var(--border-subtle)',
        border: '1px solid var(--border)',
        color: '#94a3b8', fontSize: 15, fontWeight: 500,
        fontFamily: 'var(--font-mono)',
      }

  return (
    <>
      {/* Badges */}
      <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
        <span style={{
          padding: '3px 10px', borderRadius: 4,
          background: status.bg, border: `1px solid ${status.color}28`,
          color: status.color, fontSize: 15, fontWeight: 700,
          letterSpacing: '0.12em', fontFamily: 'var(--font-mono)',
        }}>{status.label}</span>
        <span style={{
          padding: '3px 10px', borderRadius: 4,
          background: priority.bg, border: `1px solid ${priority.color}28`,
          color: priority.color, fontSize: 15, fontWeight: 700,
          letterSpacing: '0.12em', fontFamily: 'var(--font-mono)',
        }}>{priority.label}</span>
        {task.deadline && (
          <span style={deadlineBadgeStyle}>⏱ {task.deadline}</span>
        )}
        {task.blocked_by && task.blocked_by.length > 0 && (
          <span style={{
            padding: '3px 10px', borderRadius: 4,
            background: 'rgba(244,63,94,0.1)',
            border: '1px solid rgba(244,63,94,0.28)',
            color: '#f43f5e', fontSize: 15, fontWeight: 700,
            letterSpacing: '0.08em', fontFamily: 'var(--font-mono)',
          }}>BLOCKED</span>
        )}
      </div>

      <div style={{ height: 1, background: 'var(--border-subtle)', flexShrink: 0 }} />

      {/* Description */}
      {task.description && (
        <p style={{ margin: 0, color: 'var(--text-2)', fontSize: 22, lineHeight: 1.65 }}>
          {task.description}
        </p>
      )}

      {/* Assigned researcher */}
      {task.assignee_id && (
        <div>
          <span style={labelStyle}>Assigned Researcher</span>
          <span style={{ color: 'var(--text-2)', fontSize: 18 }}>
            {members.find(m => m.user_id === task.assignee_id)?.username ?? task.assignee_id}
          </span>
        </div>
      )}

      {/* Linked session */}
      {task.session_id && (
        <div style={{
          background: 'rgba(255,128,21,0.04)',
          border: '1px solid rgba(255,128,21,0.14)',
          borderRadius: 8, padding: '12px 14px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 9 }}>
            <span style={{
              width: 5, height: 5, borderRadius: '50%',
              background: '#ff8015', boxShadow: '0 0 5px #ff8015',
            }} />
            <span style={{
              fontSize: 15, fontWeight: 700, color: '#ff8015',
              letterSpacing: '0.12em', fontFamily: 'var(--font-mono)',
            }}>LINKED SESSION</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <code style={{
              flex: 1, fontSize: 20, color: 'var(--text-2)',
              fontFamily: 'var(--font-mono)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {task.session_id}
            </code>
            <button
              onClick={onCopySessionId}
              style={{
                flexShrink: 0, padding: '3px 10px', fontSize: 16, cursor: 'pointer',
                background: copied ? 'rgba(16,185,129,0.12)' : 'rgba(255,128,21,0.08)',
                border: `1px solid ${copied ? 'rgba(16,185,129,0.28)' : 'rgba(255,128,21,0.22)'}`,
                borderRadius: 5, color: copied ? '#10b981' : '#ff8015',
                fontFamily: 'var(--font-mono)', transition: 'all 0.2s',
              }}
            >{copied ? '✓ Copied' : 'Copy'}</button>
          </div>
          <p style={{
            margin: '7px 0 0', fontSize: 16, color: 'var(--text-dim)',
            fontFamily: 'var(--font-mono)',
          }}>
            EvoSci --resume {task.session_id}
          </p>
        </div>
      )}

      {/* Dependencies */}
      {token && (
        <DependencyPicker
          projectId={projectId}
          taskId={task.id}
          token={token}
          allTasks={allTasks}
        />
      )}
    </>
  )
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/components/__tests__/TaskDetailView.test.tsx
```

Expected: 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/frontend/src/components/task/TaskDetailView.tsx \
        EvoScientist/pm/frontend/src/components/__tests__/TaskDetailView.test.tsx
git commit -m "feat(pm): add TaskDetailView component for task drawer DETAILS tab"
```

---

## Task 4: Create `TaskEditForm.tsx` with tests

**Files:**
- Create: `EvoScientist/pm/frontend/src/components/task/TaskEditForm.tsx`
- Create: `EvoScientist/pm/frontend/src/components/__tests__/TaskEditForm.test.tsx`

- [ ] **Step 1: Write the failing tests**

```typescript
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/components/__tests__/TaskEditForm.test.tsx
```

Expected: FAIL — `Cannot find module '../task/TaskEditForm'`

- [ ] **Step 3: Create `TaskEditForm.tsx`**

```typescript
// EvoScientist/pm/frontend/src/components/task/TaskEditForm.tsx
import React from 'react'
import { DeadlinePicker } from '../DeadlinePicker'
import { inputStyle, selectStyle, labelStyle } from './taskStyles'
import type { Task, Member } from '../../api'

interface Props {
  editTitle: string;        setEditTitle: (v: string) => void
  editStatus: Task['status']; setEditStatus: (v: Task['status']) => void
  editPriority: Task['priority']; setEditPriority: (v: Task['priority']) => void
  editDeadline: string;     setEditDeadline: (v: string) => void
  editDescription: string;  setEditDescription: (v: string) => void
  editAssigneeId: string;   setEditAssigneeId: (v: string) => void
  onSave: () => void
  onDeleteClick: () => void
  isSaving: boolean
  isDeleting: boolean
  deleteConfirm: boolean
  members: Member[]
}

export function TaskEditForm({
  editTitle, setEditTitle,
  editStatus, setEditStatus,
  editPriority, setEditPriority,
  editDeadline, setEditDeadline,
  editDescription, setEditDescription,
  editAssigneeId, setEditAssigneeId,
  onSave, onDeleteClick,
  isSaving, isDeleting, deleteConfirm,
  members,
}: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <label style={labelStyle}>Experiment Title</label>
        <input
          value={editTitle}
          onChange={e => setEditTitle(e.target.value)}
          style={inputStyle}
          onFocus={e => { e.currentTarget.style.borderColor = 'rgba(255,128,21,0.3)' }}
          onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
        />
      </div>

      <div>
        <label style={labelStyle}>Protocol Status</label>
        <select
          value={editStatus}
          onChange={e => setEditStatus(e.target.value as Task['status'])}
          style={selectStyle}
        >
          <option value="todo">PLANNED</option>
          <option value="in_progress">IN PROGRESS</option>
          <option value="done">COMPLETE</option>
        </select>
      </div>

      <div>
        <label style={labelStyle}>Priority Level</label>
        <select
          value={editPriority}
          onChange={e => setEditPriority(e.target.value as Task['priority'])}
          style={selectStyle}
        >
          <option value="high">CRITICAL</option>
          <option value="medium">STANDARD</option>
          <option value="low">ROUTINE</option>
        </select>
      </div>

      <div>
        <label style={labelStyle}>Deadline</label>
        <DeadlinePicker
          value={editDeadline}
          onChange={setEditDeadline}
          inputStyle={inputStyle}
        />
      </div>

      <div>
        <label style={labelStyle}>Experiment Notes</label>
        <textarea
          value={editDescription}
          onChange={e => setEditDescription(e.target.value)}
          rows={4}
          style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.55 }}
          onFocus={e => { e.currentTarget.style.borderColor = 'rgba(255,128,21,0.3)' }}
          onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
        />
      </div>

      <div>
        <label style={labelStyle}>Assigned Researcher</label>
        <select
          value={editAssigneeId}
          onChange={e => setEditAssigneeId(e.target.value)}
          style={selectStyle}
        >
          <option value="">Unassigned</option>
          {members.map(m => (
            <option key={m.user_id} value={m.user_id}>{m.username}</option>
          ))}
        </select>
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <button
          onClick={onSave}
          disabled={isSaving}
          style={{
            flex: 1, padding: '9px 0', fontSize: 20, cursor: 'pointer',
            background: 'rgba(255,128,21,0.1)',
            border: '1px solid rgba(255,128,21,0.28)',
            borderRadius: 7, color: '#ff8015', fontWeight: 700,
            letterSpacing: '0.08em', fontFamily: 'var(--font-mono)',
            transition: 'background 0.14s',
            opacity: isSaving ? 0.6 : 1,
          }}
          onMouseEnter={e => { if (!isSaving) e.currentTarget.style.background = 'rgba(255,128,21,0.2)' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.1)' }}
        >{isSaving ? 'saving…' : 'SAVE'}</button>
      </div>

      <button
        onClick={onDeleteClick}
        disabled={isDeleting}
        style={{
          width: '100%', padding: '8px 0', fontSize: 20, cursor: 'pointer',
          background: deleteConfirm ? 'rgba(244,63,94,0.15)' : 'rgba(244,63,94,0.07)',
          border: `1px solid ${deleteConfirm ? 'rgba(244,63,94,0.4)' : 'rgba(244,63,94,0.2)'}`,
          borderRadius: 7, color: '#f43f5e', fontWeight: 700,
          letterSpacing: '0.08em', fontFamily: 'var(--font-mono)',
          transition: 'all 0.18s',
        }}
      >{deleteConfirm ? 'CONFIRM DELETE ?' : 'DELETE'}</button>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/components/__tests__/TaskEditForm.test.tsx
```

Expected: 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/frontend/src/components/task/TaskEditForm.tsx \
        EvoScientist/pm/frontend/src/components/__tests__/TaskEditForm.test.tsx
git commit -m "feat(pm): add TaskEditForm component for task drawer EDIT tab"
```

---

## Task 5: Refactor `TaskDetail.tsx` to 4-tab orchestrator

**Files:**
- Modify: `EvoScientist/pm/frontend/src/pages/TaskDetail.tsx`
- Modify: `EvoScientist/pm/frontend/src/pages/__tests__/TaskDetail.test.tsx`

- [ ] **Step 1: Update `TaskDetail.test.tsx` mocks and assertions**

Replace the entire contents of `src/pages/__tests__/TaskDetail.test.tsx` with:

```typescript
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
vi.mock('../components/task/TaskDetailView', () => ({
  TaskDetailView: ({ task }: { task: { title: string; blocked_by?: string[] } }) => (
    <div data-testid="details-tab">
      <span>{task.title}</span>
      {task.blocked_by?.length ? <span>BLOCKED</span> : null}
    </div>
  ),
}))

vi.mock('../components/task/LabNotesTab', () => ({
  LabNotesTab: () => <div data-testid="notes-tab">Notes</div>,
}))

vi.mock('../components/task/TaskEditForm', () => ({
  TaskEditForm: ({ editTitle }: { editTitle: string }) => (
    <div data-testid="edit-tab">
      <input defaultValue={editTitle} />
    </div>
  ),
}))

vi.mock('../components/AiRunsTab', () => ({
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
```

- [ ] **Step 2: Run updated tests to confirm they fail**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/pages/__tests__/TaskDetail.test.tsx
```

Expected: Several tests fail because `TaskDetail` still has the old 2-tab structure.

- [ ] **Step 3: Rewrite `TaskDetail.tsx` as 4-tab orchestrator**

Replace the entire contents of `src/pages/TaskDetail.tsx`:

```typescript
// EvoScientist/pm/frontend/src/pages/TaskDetail.tsx
import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Task, Member } from '../api'
import { AiRunsTab } from '../components/AiRunsTab'
import { TaskDetailView } from '../components/task/TaskDetailView'
import { LabNotesTab } from '../components/task/LabNotesTab'
import { TaskEditForm } from '../components/task/TaskEditForm'
import { useAuth } from '../auth'

interface Props {
  task: Task
  projectId: string
  onClose: () => void
  members: Member[]
}

type Tab = 'details' | 'notes' | 'ai' | 'edit'

export function TaskDetail({ task, projectId, onClose, members }: Props) {
  const queryClient = useQueryClient()
  const { token } = useAuth()

  // ── Active tab ──────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<Tab>('details')

  // ── Queries ─────────────────────────────────────────────────────────────────
  const { data: allTasksData = [] } = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => api.listTasks(projectId),
  })
  const allTasks = allTasksData.map((t: Task) => ({ id: t.id, title: t.title }))

  const { data: comments = [] } = useQuery({
    queryKey: ['comments', task.id],
    queryFn: () => api.listComments(projectId, task.id),
  })

  // ── Edit field state (kept in sync with task prop) ──────────────────────────
  const [editTitle,       setEditTitle]       = useState(task.title)
  const [editStatus,      setEditStatus]      = useState<Task['status']>(task.status)
  const [editPriority,    setEditPriority]    = useState<Task['priority']>(task.priority)
  const [editDeadline,    setEditDeadline]    = useState(task.deadline ?? '')
  const [editDescription, setEditDescription] = useState(task.description ?? '')
  const [editAssigneeId,  setEditAssigneeId]  = useState(task.assignee_id ?? '')

  useEffect(() => {
    setEditTitle(task.title)
    setEditStatus(task.status)
    setEditPriority(task.priority)
    setEditDeadline(task.deadline ?? '')
    setEditDescription(task.description ?? '')
    setEditAssigneeId(task.assignee_id ?? '')
  }, [task])

  // ── Comment state ───────────────────────────────────────────────────────────
  const [commentBody, setCommentBody] = useState('')

  // ── Delete confirmation ─────────────────────────────────────────────────────
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const deleteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Copy state ──────────────────────────────────────────────────────────────
  const [copied, setCopied] = useState(false)
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current)
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
    }
  }, [])

  // ── Mutations ───────────────────────────────────────────────────────────────
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
      setActiveTab('details')
    },
  })

  const deleteTask = useMutation({
    mutationFn: () => api.deleteTask(projectId, task.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      onClose()
    },
  })

  // ── Handlers ────────────────────────────────────────────────────────────────
  async function handleCopySessionId() {
    if (!task.session_id) return
    try {
      await navigator.clipboard.writeText(task.session_id)
      setCopied(true)
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
      copyTimerRef.current = setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard unavailable in non-https context
    }
  }

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

  // ── Tab bar helper ───────────────────────────────────────────────────────────
  function tabBtn(id: Tab, label: string) {
    const active = activeTab === id
    return (
      <button
        onClick={() => setActiveTab(id)}
        style={{
          padding: '4px 10px', fontSize: 15, fontFamily: 'var(--font-mono)',
          color: active ? '#ff8015' : 'var(--text-3)',
          background: 'none', border: 'none', borderBottomStyle: 'solid',
          borderBottomWidth: 2, borderBottomColor: active ? '#ff8015' : 'transparent',
          cursor: 'pointer', fontWeight: active ? 700 : 400,
        }}
      >{label}</button>
    )
  }

  // ── Title + BLOCKED badge (visible across all tabs) ─────────────────────────
  const blockedBy = (task as Task & { blocked_by?: string[] }).blocked_by
  const isBlocked = blockedBy && blockedBy.length > 0

  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'var(--overlay-bg)',
        backdropFilter: 'blur(4px)',
        display: 'flex', justifyContent: 'flex-end',
        zIndex: 100,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--surface)',
          borderLeft: '1px solid var(--border)',
          boxShadow: '-6px 0 24px rgba(0,0,0,0.12)',
          width: 476, height: '100%', overflowY: 'auto',
          padding: '28px 28px 32px',
          animation: 'slideInRight 0.2s ease',
          display: 'flex', flexDirection: 'column', gap: 20,
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Title row */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          <h2 style={{
            flex: 1, margin: 0, fontSize: 24, fontWeight: 600,
            color: 'var(--text-heading)', lineHeight: 1.35,
            display: 'flex', alignItems: 'flex-start', gap: 8, flexWrap: 'wrap',
          }}>
            <span>{task.title}</span>
            {isBlocked && (
              <span style={{
                fontSize: 13, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
                background: 'rgba(244,63,94,0.1)', border: '1px solid rgba(244,63,94,0.28)',
                color: '#f43f5e', fontFamily: 'var(--font-mono)',
                letterSpacing: '0.08em', whiteSpace: 'nowrap', alignSelf: 'center',
              }}>BLOCKED</span>
            )}
          </h2>
          <button
            onClick={onClose}
            style={{
              flexShrink: 0, cursor: 'pointer',
              background: 'var(--border-subtle)', border: '1px solid var(--border)',
              borderRadius: 6, color: 'var(--text-3)',
              width: 28, height: 28, fontSize: 21, lineHeight: 1,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'color 0.14s, border-color 0.14s',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = '#f43f5e'; e.currentTarget.style.borderColor = 'rgba(244,63,94,0.28)' }}
            onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-3)'; e.currentTarget.style.borderColor = 'var(--border)' }}
          >✕</button>
        </div>

        {/* Tab bar */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', marginBottom: 8 }}>
          {tabBtn('details', 'DETAILS')}
          {tabBtn('notes',   'NOTES')}
          {tabBtn('ai',      '⬡ AI RUNS')}
          {tabBtn('edit',    'EDIT')}
        </div>

        {/* Tab content */}
        {activeTab === 'details' && (
          <TaskDetailView
            task={task}
            projectId={projectId}
            members={members}
            token={token}
            allTasks={allTasks}
            copied={copied}
            onCopySessionId={handleCopySessionId}
          />
        )}

        {activeTab === 'notes' && (
          <LabNotesTab
            comments={comments}
            commentBody={commentBody}
            setCommentBody={setCommentBody}
            onSubmit={() => addComment.mutate(commentBody)}
            isPending={addComment.isPending}
          />
        )}

        {activeTab === 'ai' && (
          <AiRunsTab task={task} projectId={projectId} />
        )}

        {activeTab === 'edit' && (
          <TaskEditForm
            editTitle={editTitle}         setEditTitle={setEditTitle}
            editStatus={editStatus}       setEditStatus={setEditStatus}
            editPriority={editPriority}   setEditPriority={setEditPriority}
            editDeadline={editDeadline}   setEditDeadline={setEditDeadline}
            editDescription={editDescription} setEditDescription={setEditDescription}
            editAssigneeId={editAssigneeId}   setEditAssigneeId={setEditAssigneeId}
            onSave={handleSave}
            onDeleteClick={handleDeleteClick}
            isSaving={updateTask.isPending}
            isDeleting={deleteTask.isPending}
            deleteConfirm={deleteConfirm}
            members={members}
          />
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run updated TaskDetail tests**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/pages/__tests__/TaskDetail.test.tsx
```

Expected: 7 tests PASS

- [ ] **Step 5: Run the full frontend test suite**

```bash
cd EvoScientist/pm/frontend && npx vitest run
```

Expected: All tests pass (no regressions).

- [ ] **Step 6: Commit**

```bash
git add EvoScientist/pm/frontend/src/pages/TaskDetail.tsx \
        EvoScientist/pm/frontend/src/pages/__tests__/TaskDetail.test.tsx
git commit -m "refactor(pm): split TaskDetail into 4-tab orchestrator with DETAILS/NOTES/AI/EDIT tabs"
```

---

## Task 6: Run backend tests and final validation

- [ ] **Step 1: Run backend PM tests**

```bash
uv run pytest tests/pm/ --timeout=30 -q
```

Expected: 164 passed (no regressions — no backend was touched)

- [ ] **Step 2: Run full frontend suite one more time**

```bash
cd EvoScientist/pm/frontend && npx vitest run
```

Expected: All tests pass.

- [ ] **Step 3: Final commit if any stray changes remain**

```bash
git status
# If clean, nothing to do. Otherwise:
git add -p && git commit -m "chore(pm): clean up after TaskDetail refactor"
```
