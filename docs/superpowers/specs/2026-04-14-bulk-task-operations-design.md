# Bulk Task Operations — Design Spec

**Date:** 2026-04-14
**Scope:** Frontend only — no backend or API changes.
**Goal:** Allow users to select multiple tasks on the Board and apply a status or phase change to all of them at once.

---

## Motivation

Researchers frequently need to move a batch of tasks to the next phase or mark a sprint of tasks as complete. Doing this one-by-one through the drawer is tedious. Bulk operations eliminate that friction without adding destructive actions (no bulk delete).

---

## UX

### Selection

- Each `DraggableCard` shows a checkbox in the top-left corner **on hover or when selected**.
- Clicking the checkbox toggles selection; it does **not** open the task drawer.
- The checkbox stops pointer/drag event propagation so it doesn't interfere with DnD.
- Selected cards get a subtle highlight border (orange tint).

### Bulk Action Bar

- A `BulkActionBar` component renders **fixed at the bottom** of the board whenever `selectedIds.size > 0`.
- It shows: `N selected` count, a **Status** dropdown (PLANNED / IN PROGRESS / COMPLETE), a **Phase** dropdown (populated from the existing `phases` query — includes a "No phase" option), and a `✕ Clear` button.
- Selecting a value from either dropdown immediately applies it to all selected tasks in parallel, then clears the selection.
- The bar disappears when selection is cleared.

---

## File Structure

**New files:**
- `src/components/board/BulkActionBar.tsx` — floating toolbar (~80 lines)
- `src/components/board/__tests__/BulkActionBar.test.tsx`
- `src/components/board/__tests__/DraggableCard.test.tsx`

**Modified files:**
- `src/pages/Board.tsx` — add `selectedIds` state + bulk mutation handlers + render `BulkActionBar`
- `src/components/board/DraggableCard.tsx` — add `isSelected` + `onToggleSelect` props + checkbox rendering

---

## Component Responsibilities

### `BulkActionBar.tsx`

Pure display component. No queries, no mutations, no local state.

**Props:**
```typescript
interface Props {
  count: number
  phases: { id: string; name: string }[]
  onStatusChange: (status: Task['status']) => void
  onPhaseChange: (phaseId: string | null) => void
  onClear: () => void
}
```

Renders: count badge, status `<select>` (empty default option as placeholder), phase `<select>` (includes "No phase" → `null`), clear button.

Selecting a value from either dropdown calls the corresponding handler immediately (no separate "Apply" button).

### `DraggableCard.tsx` (modified)

Two new props added:
```typescript
isSelected: boolean
onToggleSelect: (taskId: string) => void
```

- Checkbox rendered in top-left on hover or when `isSelected` is true.
- Checkbox `onClick` calls `onToggleSelect(task.id)` and stops propagation.
- Selected card gets `border: '1px solid rgba(255,128,21,0.45)'` to visually distinguish it.

### `Board.tsx` (modified)

New state:
```typescript
const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
```

New callbacks:
```typescript
function toggleSelect(taskId: string) {
  setSelectedIds(prev => {
    const next = new Set(prev)
    next.has(taskId) ? next.delete(taskId) : next.add(taskId)
    return next
  })
}
```

New bulk mutation handler (fires parallel `api.updateTask` calls):
```typescript
async function applyBulkUpdate(updates: Partial<Task>) {
  await Promise.all(
    [...selectedIds].map(id => api.updateTask(projectId!, id, updates))
  )
  queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
  setSelectedIds(new Set())
}
```

Renders `<BulkActionBar>` conditionally when `selectedIds.size > 0`, passing `phases`, `onStatusChange`, `onPhaseChange`, `onClear`.

---

## Data Flow

```
Board (selectedIds state + applyBulkUpdate)
  │
  ├── DraggableCard (isSelected, onToggleSelect) × N
  │     └── checkbox onClick → toggleSelect(task.id)
  │
  └── BulkActionBar (count, phases, onStatusChange, onPhaseChange, onClear)
        └── dropdown onChange → applyBulkUpdate({ status }) or applyBulkUpdate({ phase_id })
```

---

## Testing

| File | Tests |
|------|-------|
| `BulkActionBar.test.tsx` | renders count; status dropdown calls `onStatusChange` with correct value; phase dropdown calls `onPhaseChange` with correct value; clear button calls `onClear`; not rendered when count is 0 (N/A — caller controls this, tested in Board) |
| `DraggableCard.test.tsx` | checkbox visible when `isSelected=true`; clicking checkbox calls `onToggleSelect` with task id; clicking checkbox does not call `onCardClick`; selected card has highlighted border style |
| `Board.test.tsx` (2 new) | selecting a card renders BulkActionBar with count 1; clearing selection hides BulkActionBar |

---

## Non-Goals

- No bulk delete
- No backend changes
- No "select all" button (YAGNI — can add later if needed)
- No undo for bulk operations
