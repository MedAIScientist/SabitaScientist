# TaskDetail Refactor & UX Redesign — Design Spec

**Date:** 2026-04-14
**Scope:** Frontend only — no backend or API changes.
**Goal:** Split the 631-line `TaskDetail.tsx` into focused tab-scoped components and redesign the drawer UX from a view/edit mode toggle to a four-tab layout.

---

## Motivation

`TaskDetail.tsx` currently mixes view rendering, edit form, mutations, queries, and state management in a single 631-line file. This makes it hard to extend (future tabs like audit log) and violates the 200–400 line guideline. The existing UX also replaces the entire view with an edit form, which hides task details while editing.

---

## UX Change

### Before
- Drawer opens in **view mode**
- Two tabs: `DETAILS | ⬡ AI RUNS`
- Clicking EDIT button replaces the entire view with a form
- No dedicated tab for lab notes

### After
- Drawer opens on **DETAILS tab** (default)
- Four tabs: `DETAILS | NOTES | AI RUNS | EDIT`
- Edit is a persistent tab — task details remain visible on other tabs while editing
- Lab notes (comments) get their own `NOTES` tab
- After a successful save, drawer switches back to `DETAILS` tab
- Delete button stays in the `EDIT` tab (two-click confirm, 3-second timer, identical behavior)

---

## File Structure

```
pages/
  TaskDetail.tsx                          ~200 lines  orchestrator

components/task/
  taskStyles.ts                           ~40 lines   shared constants and style objects
  TaskDetailView.tsx                      ~150 lines  DETAILS tab
  TaskEditForm.tsx                        ~130 lines  EDIT tab
  LabNotesTab.tsx                         ~120 lines  NOTES tab

components/
  AiRunsTab.tsx                           unchanged
```

### New directory: `components/task/`

Groups the four tab-scoped components together. `taskStyles.ts` lives here so constants aren't duplicated across files.

---

## Component Responsibilities

### `TaskDetail.tsx` (orchestrator)

**Owns:**
- Drawer shell: fixed overlay + slide-in panel JSX
- Tab bar: renders `DETAILS | NOTES | AI RUNS | EDIT` buttons
- `activeTab` state — defaults to `'details'`
- All TanStack Query hooks: `allTasks`, `comments`
- All mutations: `updateTask`, `deleteTask`, `addComment`
- Edit field state: `editTitle`, `editStatus`, `editPriority`, `editDeadline`, `editDescription`, `editAssigneeId`
- Delete confirmation state: `deleteConfirm` + `deleteTimerRef`
- Copy state: `copied` + `copyTimerRef`
- Timer cleanup `useEffect`
- `useAuth` hook call

**Does not render:** any tab content directly — delegates to tab components.

**On successful `updateTask`:** calls `setActiveTab('details')`.

---

### `taskStyles.ts`

Exports shared style constants used across tab components:
- `STATUS_META`
- `PRIORITY_META`
- `inputStyle`
- `selectStyle`
- `labelStyle`
- `isOverdue(deadline)`

---

### `TaskDetailView.tsx` (DETAILS tab)

**Props:**
```typescript
interface Props {
  task: Task
  projectId: string
  members: Member[]
  token: string | null
  allTasks: { id: string; title: string }[]
  copied: boolean
  onCopySessionId: () => void
}
```

**Renders:** status/priority/deadline badges, description, assignee, linked session card (with copy button), `DependencyPicker`.

No local state. No queries. No mutations.

---

### `LabNotesTab.tsx` (NOTES tab)

**Props:**
```typescript
interface Props {
  comments: { id: string; body: string; created_at: string }[]
  commentBody: string
  setCommentBody: (v: string) => void
  onSubmit: () => void
  isPending: boolean
}
```

**Renders:** comment list, empty state message, add-comment form.

No local state. No queries. No mutations.

---

### `TaskEditForm.tsx` (EDIT tab)

**Props:**
```typescript
interface Props {
  // Field values and setters
  editTitle: string;        setEditTitle: (v: string) => void
  editStatus: Task['status']; setEditStatus: (v: Task['status']) => void
  editPriority: Task['priority']; setEditPriority: (v: Task['priority']) => void
  editDeadline: string;     setEditDeadline: (v: string) => void
  editDescription: string;  setEditDescription: (v: string) => void
  editAssigneeId: string;   setEditAssigneeId: (v: string) => void
  // Actions
  onSave: () => void
  onDeleteClick: () => void
  // Status
  isSaving: boolean
  isDeleting: boolean
  deleteConfirm: boolean
  // Data
  members: Member[]
}
```

**Renders:** 6-field form (title, status, priority, deadline, description, assignee), SAVE button, DELETE button with two-click confirm.

No local state. No queries. No mutations.

---

## Data Flow

```
TaskDetail (queries + mutations + state)
  │
  ├── TaskDetailView   ← task, projectId, members, token, allTasks, copied, onCopySessionId
  ├── LabNotesTab      ← comments, commentBody, setCommentBody, onSubmit, isPending
  ├── AiRunsTab        ← task, projectId  (unchanged)
  └── TaskEditForm     ← edit fields + setters + onSave + onDeleteClick + status flags + members
```

All async state lives in `TaskDetail`. Children are pure display components — no hooks, no queries, no mutations.

---

## Tab Initialization

When the drawer opens, edit field state is initialized from `task` props immediately via `useEffect([task])` — fields stay in sync if the task re-fetches after a mutation. The `enterEditMode()` and `cancelEdit()` functions are removed; navigation is just `setActiveTab(...)`. `commentBody` lives in `TaskDetail` (not `LabNotesTab`) because the `addComment` mutation's `onSuccess` resets it to `''`.

---

## Testing

| File | Tests |
|------|-------|
| `task/TaskDetailView.test.tsx` | renders status/priority badges; renders BLOCKED badge when `blocked_by` non-empty; renders session card; copy button calls handler |
| `task/TaskEditForm.test.tsx` | renders all 6 fields; SAVE disabled while `isSaving`; first DELETE click shows confirm; second DELETE click calls `onDeleteClick` |
| `task/LabNotesTab.test.tsx` | renders comment list; renders empty state; form submit calls `onSubmit`; input disabled while `isPending` |

Existing `TaskDetail` public interface (`Props`) is unchanged — callers (`Board.tsx`) need no updates.

---

## Non-Goals

- No backend changes
- No API changes
- No behavior changes to existing features (copy, two-click delete, blocked badge, session card)
- No changes to `AiRunsTab`, `DependencyPicker`, `DeadlinePicker`
