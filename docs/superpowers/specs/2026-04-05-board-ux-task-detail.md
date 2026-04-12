# Board UX & Task Detail — Design Spec

**Goal:** Add drag-and-drop, filter toolbar, card editing popover, full task editing in the drawer (with delete), member assignment, and overdue highlighting to the EvoScientist PM kanban board.

**Architecture:** Pure frontend changes — no new API endpoints. All mutations use the existing `PATCH /projects/{id}/tasks/{task_id}` and `DELETE /projects/{id}/tasks/{task_id}` endpoints. Filtering is client-side over the already-loaded task list. Drag-and-drop uses `@dnd-kit/core`.

**Tech Stack:** React 18, `@dnd-kit/core` + `@dnd-kit/sortable` + `@dnd-kit/utilities`, TanStack Query, existing inline styles + CSS variables.

---

## Components

### Modified: `Board.tsx`

**Filter toolbar** (second row below the sticky header):
- Search input: substring match on `task.title` (case-insensitive)
- Priority chips: HIGH / MED / LOW toggle buttons — all active = no filter; any deselected = AND filter
- Sort dropdown: `Created` (default) | `Deadline` | `Priority`
- Assignee dropdown: `All` + one entry per `project.members`; filters to tasks whose `assignee_id` matches

Filter state lives in `useState` inside `Board`. The filtered/sorted task list is derived synchronously — no server calls.

**Drag-and-drop:**
- Wrap the three columns in `<DndContext onDragStart onDragOver onDragEnd>` from `@dnd-kit/core`
- Each task card is a `<SortableItem>` via `@dnd-kit/sortable`
- `onDragStart`: set `activeTaskId` in state; the source card renders at 35% opacity
- `onDragOver`: set `overColumnId` in state
- `onDragEnd`: call `PATCH` to update `status`; clear `activeTaskId` and `overColumnId`
- Drop zone visual (applied to the target column while `overColumnId === col.key`):
  - Column border: `2px solid <col.accent>` with `box-shadow: 0 0 14px rgba(<col.glow>, 0.25)`
  - Background: `rgba(<col.glow>, 0.07)`
  - A dashed ghost placeholder `div` (same height as the dragged card) appears at the insertion point inside the column card list

**Card hover edit icon:**
- Each task card tracks `isHovered` in local state via `onMouseEnter/Leave`
- While hovered, a `✎` button appears absolutely positioned at top-right of the card
- Clicking ✎ opens `CardEditPopover` anchored to that card
- Clicking the card body (not ✎) still opens `TaskDetail` as before

---

### New: `CardEditPopover.tsx` (~80 lines)

A `position: fixed` floating panel anchored near the card using a `ref` + `getBoundingClientRect()`.

**Fields:**
- Title: `<input>` (autofocused)
- Priority: `<select>` with options high / medium / low
- Deadline: `<input type="date">`

**Behaviour:**
- `Enter` or clicking SAVE calls `PATCH` via TanStack mutation → closes popover
- `Escape` dismisses without saving
- Click outside (via `useEffect` + `mousedown` listener on `document`) closes without saving
- Shows a spinner on the button while the mutation is pending

---

### Modified: `TaskDetail.tsx`

**View mode (default):**
Current read-only layout is preserved. EDIT button appears in the header (cyan, beside the ✕).

**Edit mode (toggled by EDIT):**
All fields become editable inputs:
- Title: `<input>`
- Status: `<select>` (todo / in_progress / done)
- Priority: `<select>` (high / medium / low)
- Deadline: `<input type="date">`
- Description: `<textarea>`
- Assignee: `<select>` listing project members + "Unassigned" option (maps to `assignee_id: null`)

**Save / Cancel:**
- SAVE button at the bottom calls `PATCH` with all changed fields; on success returns to view mode
- CANCEL button discards changes and returns to view mode
- EDIT button label changes to CANCEL while in edit mode

**Delete task:**
- DELETE button (rose-colored) appears at the bottom of edit mode
- First click changes button to "CONFIRM DELETE ?" with a 3-second auto-reset timeout
- Second click within 3 seconds calls `DELETE /projects/{id}/tasks/{task_id}`, closes drawer, invalidates task list

---

### Overdue highlighting

Applied to both card and drawer when `task.deadline` is a non-empty string and `new Date(task.deadline) < new Date()` (today midnight):

- **Card**: left border `3px solid #f43f5e`; deadline text color `#f43f5e`
- **Drawer badges**: deadline badge background `rgba(244,63,94,0.12)`, border `rgba(244,63,94,0.28)`, text `#f43f5e`

---

## API contract (existing endpoints used)

| Method | Path | Body fields used |
|--------|------|-----------------|
| `PATCH` | `/projects/{pid}/tasks/{tid}` | `title`, `status`, `priority`, `deadline`, `description`, `assignee_id` |
| `DELETE` | `/projects/{pid}/tasks/{tid}` | — |

`assignee_id` is already in the `Task` schema as an optional int. The backend `update_task` CRUD already accepts it. No backend changes needed.

---

## New npm dependencies

```
@dnd-kit/core
@dnd-kit/sortable
@dnd-kit/utilities
```

---

## Out of scope for this spec

- Drag-and-drop reordering *within* a column (only cross-column status change)
- Bulk actions (multi-select)
- Backend-side filtering or pagination
