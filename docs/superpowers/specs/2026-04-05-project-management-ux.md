# Project Management UX — Design Spec

**Goal:** Add project editing, project deletion, description field on create, and a full member-management panel (add / remove / change role) to the EvoScientist PM kanban tool, surfaced through a unified ⚙ Settings panel inside the Board view.

**Architecture:** Minimal backend addition (one new `GET /users/search` endpoint for authenticated users), plus pure-frontend changes for the settings panel and project-list create-form extension. All project/member mutations use existing `PUT /projects/{id}`, `DELETE /projects/{id}`, `POST /projects/{id}/members`, `PUT /projects/{id}/members/{uid}`, and `DELETE /projects/{id}/members/{uid}` endpoints.

**Tech Stack:** React 18, TanStack Query v5, existing inline styles + CSS variables, dark "Deep Lab" theme (IBM Plex Mono/Sans, `#070b12` bg, cyan/amber/emerald accents).

---

## Backend change

### New endpoint: `GET /api/v1/users/search`

**File:** `EvoScientist/pm/api/routes/users.py`

```
GET /users/search?q=<string>
```

- Requires any authenticated user (not admin-only)
- `q` is a case-insensitive prefix/substring match on `username`
- Returns `[{id: str, username: str}]` — no email, no admin flag, no password hash
- Maximum 20 results
- If `q` is empty or shorter than 1 character, returns `[]`

**New Pydantic schema** (`schemas.py`):
```python
class UserSearchResult(BaseModel):
    id: str
    username: str
```

---

## Frontend changes

### Modified: `api.ts`

Add five new functions to the `api` object:

```typescript
searchUsers: (q: string) =>
  request<{ id: string; username: string }[]>('GET', `/users/search?q=${encodeURIComponent(q)}`),
updateProject: (id: string, data: { name?: string; description?: string }) =>
  request<Project>('PUT', `/projects/${id}`, data),
deleteProject: (id: string) =>
  request<void>('DELETE', `/projects/${id}`),
removeMember: (projectId: string, userId: string) =>
  request<void>('DELETE', `/projects/${projectId}/members/${userId}`),
updateMemberRole: (projectId: string, userId: string, role: string) =>
  request<Member>('PUT', `/projects/${projectId}/members/${userId}`, { role }),
```

---

### Modified: `Projects.tsx`

Extend the create-project inline form to include an optional description field:
- A `<textarea>` below the name input, placeholder `"Brief description (optional)…"`, max 3 rows
- `createProject` call gains `description` argument: `createMutation.mutate({ name: newName, description: newDesc || undefined })`
- Update `createMutation.mutationFn` signature from `(name: string)` to `({ name, description? })` accordingly

No other changes to Projects.tsx.

---

### Modified: `Board.tsx`

In the Board header (right side, alongside the back-to-projects link):

- Determine if the current user is an owner: `const isOwner = project?.members.some(m => m.user_id === currentUser?.id && m.role === 'owner')`
- Render a `⚙ SETTINGS` button only when `isOwner` is true
- Button opens `<ProjectSettingsPanel>` via `settingsPanelOpen` boolean state
- Render `<ProjectSettingsPanel project={project} projectId={projectId} onClose={() => setSettingsPanelOpen(false)} />` when open, alongside existing `<TaskDetail>` and `<CardEditPopover>`

The `currentUser` comes from `useAuth()` (already imported in Board).

---

### New: `ProjectSettingsPanel.tsx`

**Location:** `EvoScientist/pm/frontend/src/components/ProjectSettingsPanel.tsx`

**Props:**
```typescript
interface ProjectSettingsPanelProps {
  project: Project
  projectId: string
  onClose: () => void
}
```

A `position: fixed` right drawer, same width and slide-in style as `TaskDetail` (`slideInRight` animation, width 340px, `top: 0, right: 0, height: 100vh`). Background `#070b12`, border-left `1px solid rgba(100,140,200,0.12)`.

#### Header
- Title: "PROJECT SETTINGS" in `var(--font-mono)`, cyan
- ✕ close button (calls `onClose`)

#### Section 1 — Project Details

Local edit state initialized from `project.name` and `project.description`:
- **Name input:** `<input>` pre-filled with project name (required)
- **Description textarea:** `<textarea>` pre-filled with project description (optional), 3 rows
- **SAVE button:** calls `updateProject` mutation with changed fields; on success invalidates `['project', projectId]` and `['projects']`; spinner while pending
- **DELETE PROJECT button** (rose `#f43f5e`, at bottom of section):
  - First click → changes to "CONFIRM DELETE ?" + 3-second auto-reset timeout (same pattern as task delete in TaskDetail)
  - Second click within 3 seconds → calls `deleteProject(projectId)`, then navigates to `/projects`, invalidates `['projects']`

#### Section 2 — Team Members

**Member list** (from `project.members`):
Each row shows:
- `username` + role badge (color-coded: owner=cyan, editor=amber, viewer=slate)
- **Role `<select>`** (owner/editor/viewer) — calls `updateMemberRole` on change; disabled for self (can't demote yourself)
- **Remove ✕ button** — calls `removeMember`; disabled/hidden for self (can't remove yourself)
- On mutation success: invalidates `['project', projectId]`

**ADD RESEARCHER sub-section:**
- Username `<input>` with placeholder `"Search by username…"`
  - After 300ms debounce, calls `searchUsers(value)` if value.length ≥ 1
  - Shows a `position: absolute` dropdown of up to 5 matching `{id, username}` results
  - Selecting a result fills the input and stores the `user_id` in state; clears the dropdown
- Role `<select>` with options owner / editor / viewer (default: editor)
- **ADD** button: calls `addMember(projectId, selectedUserId, role)`; on success clears input, invalidates `['project', projectId]`
- Error handling: if the user is already a member, show an inline error message below the ADD button

---

## API contract (endpoints used)

| Method | Path | Body / Params | Auth |
|--------|------|---------------|------|
| `GET` | `/users/search?q=` | query param | Any authenticated |
| `PUT` | `/projects/{id}` | `{name?, description?}` | Owner |
| `DELETE` | `/projects/{id}` | — | Owner |
| `POST` | `/projects/{id}/members` | `{user_id, role}` | Owner |
| `PUT` | `/projects/{id}/members/{uid}` | `{role}` | Owner |
| `DELETE` | `/projects/{id}/members/{uid}` | — | Owner |

---

## Role-based visibility

| UI element | owner | editor | viewer |
|------------|-------|--------|--------|
| ⚙ SETTINGS button | visible | hidden | hidden |
| ProjectSettingsPanel | accessible | — | — |
| Change member role | enabled (except self) | — | — |
| Remove member | enabled (except self) | — | — |

---

## Out of scope for this spec

- Project archiving (the backend supports it, but UI for archive/unarchive is deferred)
- Bulk member import
- User creation from within the settings panel (admin-only via Setup/Users pages)
- Per-member task assignment statistics
