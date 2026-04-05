# Project Management UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add project editing, project deletion, description field on create, and a full member-management panel (add / remove / change role) to the EvoScientist PM kanban tool, surfaced through a unified ⚙ Settings panel inside the Board view.

**Architecture:** One new backend endpoint (`GET /users/search`) accessible to all authenticated users for username lookup. Five new `api.ts` functions. One new `ProjectSettingsPanel` React component. Minimal changes to `Projects.tsx` (description textarea) and `Board.tsx` (owner check + settings button). All project/member mutations use existing backend endpoints.

**Tech Stack:** Python/FastAPI (backend), React 18, TanStack Query v5, vitest + @testing-library/react (frontend tests), pytest + FastAPI TestClient (backend tests).

---

## File Map

| File | Change |
|------|--------|
| `EvoScientist/pm/api/schemas.py` | Add `UserSearchResult` model |
| `EvoScientist/pm/crud/users.py` | Add `search_users(db_path, q)` |
| `EvoScientist/pm/api/routes/users.py` | Add `GET /users/search` route |
| `tests/pm/test_api_users.py` | New file — backend tests for search endpoint |
| `EvoScientist/pm/frontend/src/api.ts` | Add 5 new API functions |
| `EvoScientist/pm/frontend/src/pages/Projects.tsx` | Add description textarea to create form |
| `EvoScientist/pm/frontend/src/components/ProjectSettingsPanel.tsx` | New component |
| `EvoScientist/pm/frontend/src/components/__tests__/ProjectSettingsPanel.test.tsx` | New test file |
| `EvoScientist/pm/frontend/src/pages/Board.tsx` | Add `useAuth`, `isOwner` check, settings button, `ProjectSettingsPanel` |
| `EvoScientist/pm/frontend/src/pages/__tests__/Board.test.tsx` | Add 2 owner-visibility tests |

---

## Task 1: Backend — `search_users` CRUD + `/users/search` route

**Files:**
- Modify: `EvoScientist/pm/api/schemas.py`
- Modify: `EvoScientist/pm/crud/users.py`
- Modify: `EvoScientist/pm/api/routes/users.py`
- Create: `tests/pm/test_api_users.py`

- [ ] **Step 1: Write the failing backend tests**

Create `tests/pm/test_api_users.py`:

```python
"""Tests for /users/search endpoint."""


def test_search_returns_empty_for_short_query(client, admin_token) -> None:
    resp = client.get(
        "/api/v1/users/search?q=",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_returns_matching_users(client, tmp_db, admin_token) -> None:
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.users import create_user

    create_user(tmp_db, username="alice_lab", password_hash=hash_password("p"))
    create_user(tmp_db, username="bob_lab", password_hash=hash_password("p"))

    resp = client.get(
        "/api/v1/users/search?q=alice",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["username"] == "alice_lab"
    assert "id" in data[0]
    # Must NOT expose email, password_hash, or is_admin
    assert "email" not in data[0]
    assert "password_hash" not in data[0]
    assert "is_admin" not in data[0]


def test_search_is_case_insensitive(client, tmp_db, admin_token) -> None:
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.users import create_user

    create_user(tmp_db, username="ALICE_LAB", password_hash=hash_password("p"))

    resp = client.get(
        "/api/v1/users/search?q=alice",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_search_requires_authentication(client) -> None:
    resp = client.get("/api/v1/users/search?q=alice")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run the failing tests**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
uv run pytest tests/pm/test_api_users.py -v 2>&1 | tail -20
```

Expected: 4 FAILs with "404 Not Found" or "not found" since the route doesn't exist yet.

- [ ] **Step 3: Add `UserSearchResult` schema**

In `EvoScientist/pm/api/schemas.py`, add after the `UserResponse` class (around line 32):

```python
class UserSearchResult(BaseModel):
    id: str
    username: str
```

- [ ] **Step 4: Add `search_users` CRUD function**

In `EvoScientist/pm/crud/users.py`, add after `list_users` (around line 66):

```python
def search_users(db_path: Path, q: str, limit: int = 20) -> list[User]:
    """Return users whose username contains q (case-insensitive), up to limit."""
    if not q:
        return []
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT id, username, email, password_hash, is_admin, created_at
               FROM users WHERE username LIKE ? ORDER BY username LIMIT ?""",
            (f"%{q}%", limit),
        ).fetchall()
    return [_row_to_user(r) for r in rows]
```

- [ ] **Step 5: Add `GET /users/search` route**

In `EvoScientist/pm/api/routes/users.py`:

1. Add `search_users` to the import from `crud.users` (line 10):
```python
from ...crud.users import (
    create_user,
    delete_user,
    get_user_by_id,
    list_users,
    search_users,
    update_user_password,
)
```

2. Add `UserSearchResult` to the import from `schemas` (line 17):
```python
from ..schemas import UpdatePasswordRequest, UserCreate, UserResponse, UserSearchResult
```

3. Add the route **before** the `/{user_id}` route (insert after the `PUT /me` route, around line 72):
```python
@router.get("/search", response_model=list[UserSearchResult])
def search_users_endpoint(
    q: str = "",
    current_user: User = Depends(get_current_user),
):
    """Search users by username substring. Accessible to any authenticated user."""
    if len(q) < 1:
        return []
    return [
        UserSearchResult(id=u.id, username=u.username)
        for u in search_users(get_db_path(), q)
    ]
```

- [ ] **Step 6: Run the tests — all 4 must pass**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
uv run pytest tests/pm/test_api_users.py -v 2>&1 | tail -20
```

Expected: 4 PASSed.

- [ ] **Step 7: Run full backend test suite to confirm no regressions**

```bash
uv run pytest tests/pm/ -q --timeout=30 2>&1 | tail -10
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add EvoScientist/pm/api/schemas.py EvoScientist/pm/crud/users.py EvoScientist/pm/api/routes/users.py tests/pm/test_api_users.py
git commit -m "feat(pm): add GET /users/search endpoint for authenticated user lookup"
```

---

## Task 2: Frontend API extensions

**Files:**
- Modify: `EvoScientist/pm/frontend/src/api.ts`

- [ ] **Step 1: Add 5 functions to the `api` object in `api.ts`**

Read `EvoScientist/pm/frontend/src/api.ts` first. Then add the five new functions inside the `api` object, after `addMember`:

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

- [ ] **Step 2: TypeScript check — no errors**

```bash
cd EvoScientist/pm/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add EvoScientist/pm/frontend/src/api.ts
git commit -m "feat(pm): add searchUsers, updateProject, deleteProject, removeMember, updateMemberRole to api"
```

---

## Task 3: Projects.tsx — description textarea

**Files:**
- Modify: `EvoScientist/pm/frontend/src/pages/Projects.tsx`

- [ ] **Step 1: Write the failing test**

There is no test file for Projects.tsx yet. Create `EvoScientist/pm/frontend/src/pages/__tests__/Projects.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, test, expect, vi, beforeEach } from 'vitest'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth'
import { Projects } from '../Projects'

vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
  useQueryClient: vi.fn(),
}))
vi.mock('react-router-dom', () => ({
  useNavigate: vi.fn(),
}))
vi.mock('../../auth', () => ({
  useAuth: vi.fn(),
}))

const mockedUseQuery = vi.mocked(useQuery)
const mockedUseMutation = vi.mocked(useMutation)
const mockedUseQueryClient = vi.mocked(useQueryClient)
const mockedUseNavigate = vi.mocked(useNavigate)
const mockedUseAuth = vi.mocked(useAuth)

beforeEach(() => {
  mockedUseAuth.mockReturnValue({ username: 'admin', isAdmin: true, token: 'tok', login: vi.fn(), logout: vi.fn() })
  mockedUseNavigate.mockReturnValue(vi.fn())
  mockedUseQueryClient.mockReturnValue({ invalidateQueries: vi.fn() } as any)
  mockedUseMutation.mockReturnValue({ mutate: vi.fn(), isPending: false } as any)
  mockedUseQuery.mockReturnValue({ data: [], isLoading: false } as any)
})

describe('Projects', () => {
  test('renders Research Projects heading', () => {
    render(<Projects />)
    expect(screen.getByText('Research Projects')).toBeInTheDocument()
  })

  test('description textarea appears in create form when creating', async () => {
    const { getByText, getByPlaceholderText } = render(<Projects />)
    getByText('+ NEW PROJECT').click()
    expect(getByPlaceholderText('Brief description (optional)…')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run the failing test**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/pages/__tests__/Projects.test.tsx 2>&1 | head -40
```

Expected: test 2 FAILs — "Unable to find element with placeholder 'Brief description (optional)…'"

- [ ] **Step 3: Add description state and textarea to Projects.tsx**

Read `EvoScientist/pm/frontend/src/pages/Projects.tsx` first. Then make these changes:

1. Add `newDesc` state beside `newName` (around line 13):
```tsx
const [newDesc, setNewDesc] = useState('')
```

2. Update `createMutation.mutationFn` signature (around line 22–29):
```tsx
const createMutation = useMutation({
  mutationFn: ({ name, description }: { name: string; description?: string }) =>
    api.createProject(name, description),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['projects'] })
    setNewName('')
    setNewDesc('')
    setCreating(false)
  },
})
```

3. Update the form `onSubmit` to pass description (around line 151):
```tsx
onSubmit={e => { e.preventDefault(); createMutation.mutate({ name: newName, description: newDesc || undefined }) }}
```

4. Add the description textarea below the name input (after the `<input ... />` for name, around line 168):
```tsx
<textarea
  value={newDesc}
  onChange={e => setNewDesc(e.target.value)}
  placeholder="Brief description (optional)…"
  rows={2}
  style={{
    flex: 1,
    padding: '6px 11px',
    background: 'rgba(7,11,18,0.65)',
    border: '1px solid rgba(34,211,238,0.2)',
    borderRadius: 6,
    color: '#e2e8f0',
    fontSize: 12,
    outline: 'none',
    resize: 'none',
    fontFamily: 'var(--font-mono)',
    width: '100%',
  }}
/>
```

Note: the form layout will need to flex-wrap or stack since there are now two inputs. Change the form's style to `flexDirection: 'column', gap: 8` and put the buttons in a row at the bottom:

The full updated form:
```tsx
{creating ? (
  <form
    onSubmit={e => { e.preventDefault(); createMutation.mutate({ name: newName, description: newDesc || undefined }) }}
    style={{
      display: 'flex', flexDirection: 'column', gap: 8, padding: 14,
      background: 'rgba(13,21,38,0.65)',
      border: '1px solid rgba(34,211,238,0.18)',
      borderRadius: 8, animation: 'fadeInUp 0.18s ease',
    }}
  >
    <input
      autoFocus value={newName}
      onChange={e => setNewName(e.target.value)}
      placeholder="Project name…" required
      style={{
        padding: '8px 11px',
        background: 'rgba(7,11,18,0.65)',
        border: '1px solid rgba(34,211,238,0.2)',
        borderRadius: 6, color: '#e2e8f0', fontSize: 13, outline: 'none',
      }}
    />
    <textarea
      value={newDesc}
      onChange={e => setNewDesc(e.target.value)}
      placeholder="Brief description (optional)…"
      rows={2}
      style={{
        padding: '6px 11px',
        background: 'rgba(7,11,18,0.65)',
        border: '1px solid rgba(34,211,238,0.2)',
        borderRadius: 6, color: '#e2e8f0', fontSize: 12, outline: 'none',
        resize: 'none', fontFamily: 'inherit',
      }}
    />
    <div style={{ display: 'flex', gap: 8 }}>
      <button type="submit" disabled={createMutation.isPending} style={{
        padding: '8px 16px', cursor: 'pointer',
        background: '#22d3ee', color: '#070b12',
        border: 'none', borderRadius: 6, fontSize: 10, fontWeight: 700,
        letterSpacing: '0.06em', fontFamily: 'var(--font-mono)',
      }}>CREATE</button>
      <button type="button" onClick={() => setCreating(false)} style={{
        padding: '8px 12px', cursor: 'pointer',
        background: 'rgba(100,140,200,0.07)',
        border: '1px solid rgba(100,140,200,0.13)',
        borderRadius: 6, color: '#475569', fontSize: 12,
      }}>✕</button>
    </div>
  </form>
) : (
```

- [ ] **Step 4: Run all frontend tests — all must pass**

```bash
cd EvoScientist/pm/frontend && npx vitest run 2>&1 | tail -20
```

Expected: all 40 tests pass (38 existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/frontend/src/pages/Projects.tsx EvoScientist/pm/frontend/src/pages/__tests__/Projects.test.tsx
git commit -m "feat(pm): add description field to project create form"
```

---

## Task 4: `ProjectSettingsPanel` component

**Files:**
- Create: `EvoScientist/pm/frontend/src/components/ProjectSettingsPanel.tsx`
- Create: `EvoScientist/pm/frontend/src/components/__tests__/ProjectSettingsPanel.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `EvoScientist/pm/frontend/src/components/__tests__/ProjectSettingsPanel.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi, beforeEach } from 'vitest'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../../auth'
import { ProjectSettingsPanel } from '../ProjectSettingsPanel'
import type { Project } from '../../../api'

vi.mock('@tanstack/react-query', () => ({
  useMutation: vi.fn(),
  useQuery: vi.fn(),
  useQueryClient: vi.fn(),
}))
vi.mock('react-router-dom', () => ({
  useNavigate: vi.fn(),
}))
vi.mock('../../../auth', () => ({
  useAuth: vi.fn(),
}))
vi.mock('../../../api', () => ({
  api: {
    updateProject: vi.fn(),
    deleteProject: vi.fn(),
    updateMemberRole: vi.fn(),
    removeMember: vi.fn(),
    addMember: vi.fn(),
    searchUsers: vi.fn(() => Promise.resolve([])),
  },
}))

const mockedUseMutation = vi.mocked(useMutation)
const mockedUseQuery = vi.mocked(useQuery)
const mockedUseQueryClient = vi.mocked(useQueryClient)
const mockedUseNavigate = vi.mocked(useNavigate)
const mockedUseAuth = vi.mocked(useAuth)

const MOCK_PROJECT: Project = {
  id: 'proj-1',
  name: 'CRISPR Study',
  description: 'Gene editing experiments',
  created_by: 'u1',
  created_at: '2024-01-01T00:00:00Z',
  archived_at: null,
  members: [
    { user_id: 'u1', username: 'dr_chen', role: 'owner', added_at: '2024-01-01T00:00:00Z' },
    { user_id: 'u2', username: 'lab_tech', role: 'editor', added_at: '2024-01-01T00:00:00Z' },
  ],
}

function renderPanel(onClose = vi.fn()) {
  return render(
    <ProjectSettingsPanel
      project={MOCK_PROJECT}
      projectId="proj-1"
      onClose={onClose}
    />
  )
}

beforeEach(() => {
  mockedUseAuth.mockReturnValue({ username: 'dr_chen', isAdmin: false, token: 'tok', login: vi.fn(), logout: vi.fn() })
  mockedUseNavigate.mockReturnValue(vi.fn())
  mockedUseQueryClient.mockReturnValue({ invalidateQueries: vi.fn() } as any)
  mockedUseMutation.mockReturnValue({ mutate: vi.fn(), isPending: false } as any)
  mockedUseQuery.mockReturnValue({ data: [] } as any)
})

describe('ProjectSettingsPanel', () => {
  test('renders PROJECT SETTINGS title', () => {
    renderPanel()
    expect(screen.getByText('PROJECT SETTINGS')).toBeInTheDocument()
  })

  test('renders project name input pre-filled', () => {
    renderPanel()
    const input = screen.getByDisplayValue('CRISPR Study')
    expect(input).toBeInTheDocument()
  })

  test('renders description textarea pre-filled', () => {
    renderPanel()
    expect(screen.getByDisplayValue('Gene editing experiments')).toBeInTheDocument()
  })

  test('renders both member usernames', () => {
    renderPanel()
    expect(screen.getByText('dr_chen')).toBeInTheDocument()
    expect(screen.getByText('lab_tech')).toBeInTheDocument()
  })

  test('clicking DELETE PROJECT once shows CONFIRM DELETE ?', () => {
    renderPanel()
    const deleteBtn = screen.getByRole('button', { name: /delete project/i })
    fireEvent.click(deleteBtn)
    expect(screen.getByRole('button', { name: /confirm delete/i })).toBeInTheDocument()
  })

  test('self member row (dr_chen) has remove button disabled', () => {
    renderPanel()
    // dr_chen is the current user (useAuth returns dr_chen)
    // Find the remove button in dr_chen's row — it should be disabled
    const removeButtons = screen.getAllByRole('button', { name: /✕/ })
    // dr_chen is first member; its remove button should be disabled
    expect(removeButtons[0]).toBeDisabled()
  })

  test('other member row (lab_tech) has remove button enabled', () => {
    renderPanel()
    const removeButtons = screen.getAllByRole('button', { name: /✕/ })
    expect(removeButtons[1]).not.toBeDisabled()
  })

  test('renders ADD RESEARCHER username search input', () => {
    renderPanel()
    expect(screen.getByPlaceholderText('Search by username…')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run the failing tests**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/components/__tests__/ProjectSettingsPanel.test.tsx 2>&1 | head -40
```

Expected: 8 FAILs — "ProjectSettingsPanel is not defined".

- [ ] **Step 3: Implement `ProjectSettingsPanel.tsx`**

Create `EvoScientist/pm/frontend/src/components/ProjectSettingsPanel.tsx`:

```tsx
import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, Project, Member } from '../api'
import { useAuth } from '../auth'

interface ProjectSettingsPanelProps {
  project: Project
  projectId: string
  onClose: () => void
}

const ROLE_COLORS: Record<string, string> = {
  owner: '#22d3ee',
  editor: '#f59e0b',
  viewer: '#64748b',
}

const labelStyle: React.CSSProperties = {
  fontSize: 9,
  color: '#3d4e64',
  fontFamily: 'var(--font-mono)',
  letterSpacing: '0.1em',
  display: 'block',
  marginBottom: 3,
  marginTop: 10,
  textTransform: 'uppercase',
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  background: '#070b12',
  border: '1px solid rgba(100,140,200,0.18)',
  borderRadius: 4,
  color: '#f1f5f9',
  padding: '5px 8px',
  fontSize: 11,
  fontFamily: 'var(--font-mono)',
  boxSizing: 'border-box',
  outline: 'none',
}

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  cursor: 'pointer',
}

export function ProjectSettingsPanel({ project, projectId, onClose }: ProjectSettingsPanelProps) {
  const { username } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // ── Project details state ──────────────────────────────────────────────────
  const [editName, setEditName] = useState(project.name)
  const [editDesc, setEditDesc] = useState(project.description ?? '')
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const deleteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Add member state ───────────────────────────────────────────────────────
  const [searchQ, setSearchQ] = useState('')
  const [searchResults, setSearchResults] = useState<{ id: string; username: string }[]>([])
  const [selectedUser, setSelectedUser] = useState<{ id: string; username: string } | null>(null)
  const [addRole, setAddRole] = useState<'owner' | 'editor' | 'viewer'>('editor')
  const [addError, setAddError] = useState<string | null>(null)
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const dropdownRef = useRef<HTMLDivElement | null>(null)

  // ── Cleanup on unmount ─────────────────────────────────────────────────────
  useEffect(() => () => {
    if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current)
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
  }, [])

  // ── Close on Escape ────────────────────────────────────────────────────────
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onCloseRef.current()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [])

  // ── Mutations ──────────────────────────────────────────────────────────────
  const updateProject = useMutation({
    mutationFn: (data: { name?: string; description?: string }) =>
      api.updateProject(projectId, data),
    onSuccess: () => {
      setSaveError(null)
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
    onError: () => setSaveError('Save failed — please retry.'),
  })

  const deleteProject = useMutation({
    mutationFn: () => api.deleteProject(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      navigate('/projects')
    },
  })

  const removeMember = useMutation({
    mutationFn: (userId: string) => api.removeMember(projectId, userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['project', projectId] }),
  })

  const updateMemberRole = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      api.updateMemberRole(projectId, userId, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['project', projectId] }),
  })

  const addMember = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      api.addMember(projectId, userId, role),
    onSuccess: () => {
      setAddError(null)
      setSearchQ('')
      setSelectedUser(null)
      setSearchResults([])
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
    },
    onError: () => setAddError('Could not add researcher — they may already be a member.'),
  })

  // ── Handlers ───────────────────────────────────────────────────────────────
  const handleSave = useCallback(() => {
    setSaveError(null)
    updateProject.mutate({ name: editName.trim() || project.name, description: editDesc || undefined })
  }, [editName, editDesc, project.name, updateProject])

  const handleDeleteClick = useCallback(() => {
    if (!deleteConfirm) {
      setDeleteConfirm(true)
      deleteTimerRef.current = setTimeout(() => setDeleteConfirm(false), 3000)
    } else {
      if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current)
      deleteProject.mutate()
    }
  }, [deleteConfirm, deleteProject])

  const handleSearchChange = useCallback((value: string) => {
    setSearchQ(value)
    setSelectedUser(null)
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    if (value.length >= 1) {
      searchTimerRef.current = setTimeout(async () => {
        try {
          const results = await api.searchUsers(value)
          setSearchResults(results.slice(0, 5))
        } catch {
          setSearchResults([])
        }
      }, 300)
    } else {
      setSearchResults([])
    }
  }, [])

  const handleSelectUser = useCallback((user: { id: string; username: string }) => {
    setSelectedUser(user)
    setSearchQ(user.username)
    setSearchResults([])
  }, [])

  const handleAddMember = useCallback(() => {
    if (!selectedUser) return
    setAddError(null)
    addMember.mutate({ userId: selectedUser.id, role: addRole })
  }, [selectedUser, addRole, addMember])

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, width: 340, height: '100vh',
      background: '#070b12',
      borderLeft: '1px solid rgba(100,140,200,0.12)',
      display: 'flex', flexDirection: 'column',
      animation: 'slideInRight 0.22s ease',
      zIndex: 50, overflowY: 'auto',
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 16px', borderBottom: '1px solid rgba(100,140,200,0.08)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        flexShrink: 0,
      }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700, color: '#22d3ee', letterSpacing: '0.08em' }}>
          PROJECT SETTINGS
        </span>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', color: '#475569', fontSize: 14, cursor: 'pointer', padding: '2px 6px' }}
        >✕</button>
      </div>

      <div style={{ padding: '0 16px 24px', flex: 1 }}>

        {/* ── Section 1: Project Details ── */}
        <div style={{ borderBottom: '1px solid rgba(100,140,200,0.07)', paddingBottom: 16, marginBottom: 16 }}>
          <div style={{ marginTop: 14, fontSize: 10, color: '#3d4e64', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', fontWeight: 700 }}>
            PROJECT DETAILS
          </div>

          <label style={labelStyle}>NAME</label>
          <input
            value={editName}
            onChange={e => setEditName(e.target.value)}
            style={inputStyle}
          />

          <label style={labelStyle}>DESCRIPTION</label>
          <textarea
            value={editDesc}
            onChange={e => setEditDesc(e.target.value)}
            rows={3}
            style={{ ...inputStyle, resize: 'none' }}
          />

          <button
            onClick={handleSave}
            disabled={updateProject.isPending || !editName.trim()}
            style={{
              marginTop: 10, width: '100%',
              background: 'rgba(34,211,238,0.12)',
              border: '1px solid rgba(34,211,238,0.28)',
              borderRadius: 4, padding: '6px 0',
              color: '#22d3ee', fontSize: 10, fontWeight: 700,
              fontFamily: 'var(--font-mono)', cursor: 'pointer',
              opacity: updateProject.isPending ? 0.5 : 1,
            }}
          >
            {updateProject.isPending ? 'saving…' : 'SAVE'}
          </button>
          {saveError && (
            <div style={{ marginTop: 5, fontSize: 9, color: '#f43f5e', fontFamily: 'var(--font-mono)' }}>{saveError}</div>
          )}

          <button
            onClick={handleDeleteClick}
            style={{
              marginTop: 8, width: '100%',
              background: deleteConfirm ? 'rgba(244,63,94,0.15)' : 'rgba(244,63,94,0.06)',
              border: `1px solid ${deleteConfirm ? 'rgba(244,63,94,0.45)' : 'rgba(244,63,94,0.2)'}`,
              borderRadius: 4, padding: '5px 0',
              color: '#f43f5e', fontSize: 10, fontWeight: 700,
              fontFamily: 'var(--font-mono)', cursor: 'pointer',
            }}
          >
            {deleteConfirm ? 'CONFIRM DELETE ?' : 'DELETE PROJECT'}
          </button>
        </div>

        {/* ── Section 2: Team Members ── */}
        <div style={{ fontSize: 10, color: '#3d4e64', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', fontWeight: 700, marginBottom: 10 }}>
          TEAM MEMBERS · {project.members.length}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 16 }}>
          {project.members.map((m: Member) => {
            const isSelf = m.username === username
            return (
              <div key={m.user_id} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                background: 'rgba(17,30,53,0.5)', borderRadius: 5, padding: '7px 10px',
              }}>
                <span style={{ flex: 1, fontSize: 11, color: '#e2e8f0', fontFamily: 'var(--font-mono)' }}>
                  {m.username}
                </span>
                <select
                  value={m.role}
                  disabled={isSelf}
                  onChange={e => updateMemberRole.mutate({ userId: m.user_id, role: e.target.value })}
                  style={{
                    background: '#070b12',
                    border: '1px solid rgba(100,140,200,0.14)',
                    borderRadius: 3,
                    color: ROLE_COLORS[m.role] ?? '#64748b',
                    fontSize: 9, fontWeight: 700,
                    fontFamily: 'var(--font-mono)',
                    cursor: isSelf ? 'not-allowed' : 'pointer',
                    padding: '2px 4px',
                    opacity: isSelf ? 0.5 : 1,
                  }}
                >
                  <option value="owner">OWNER</option>
                  <option value="editor">EDITOR</option>
                  <option value="viewer">VIEWER</option>
                </select>
                <button
                  disabled={isSelf}
                  onClick={() => removeMember.mutate(m.user_id)}
                  style={{
                    background: 'none',
                    border: '1px solid rgba(244,63,94,0.2)',
                    borderRadius: 3, color: '#f43f5e',
                    fontSize: 10, cursor: isSelf ? 'not-allowed' : 'pointer',
                    padding: '1px 5px',
                    opacity: isSelf ? 0.3 : 1,
                  }}
                >✕</button>
              </div>
            )
          })}
        </div>

        {/* ── Add Researcher ── */}
        <div style={{ fontSize: 10, color: '#3d4e64', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', fontWeight: 700, marginBottom: 8 }}>
          ADD RESEARCHER
        </div>

        <div style={{ position: 'relative' }}>
          <input
            value={searchQ}
            onChange={e => handleSearchChange(e.target.value)}
            placeholder="Search by username…"
            style={inputStyle}
          />
          {searchResults.length > 0 && (
            <div
              ref={dropdownRef}
              style={{
                position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100,
                background: '#0d1526',
                border: '1px solid rgba(34,211,238,0.2)',
                borderRadius: 4,
                boxShadow: '0 8px 20px rgba(0,0,0,0.4)',
              }}
            >
              {searchResults.map(u => (
                <div
                  key={u.id}
                  onClick={() => handleSelectUser(u)}
                  style={{
                    padding: '7px 10px',
                    fontSize: 11, color: '#e2e8f0',
                    fontFamily: 'var(--font-mono)',
                    cursor: 'pointer',
                    borderBottom: '1px solid rgba(100,140,200,0.07)',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'rgba(34,211,238,0.07)' }}
                  onMouseLeave={e => { e.currentTarget.style.background = '' }}
                >
                  {u.username}
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
          <select
            value={addRole}
            onChange={e => setAddRole(e.target.value as typeof addRole)}
            style={{ ...selectStyle, flex: 1 }}
          >
            <option value="owner">OWNER</option>
            <option value="editor">EDITOR</option>
            <option value="viewer">VIEWER</option>
          </select>
          <button
            onClick={handleAddMember}
            disabled={!selectedUser || addMember.isPending}
            style={{
              background: 'rgba(34,211,238,0.1)',
              border: '1px solid rgba(34,211,238,0.25)',
              borderRadius: 4, color: '#22d3ee',
              fontSize: 10, fontWeight: 700,
              fontFamily: 'var(--font-mono)',
              padding: '5px 12px',
              cursor: selectedUser ? 'pointer' : 'not-allowed',
              opacity: !selectedUser || addMember.isPending ? 0.5 : 1,
            }}
          >
            {addMember.isPending ? '…' : 'ADD'}
          </button>
        </div>
        {addError && (
          <div style={{ marginTop: 5, fontSize: 9, color: '#f43f5e', fontFamily: 'var(--font-mono)' }}>{addError}</div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run the 8 tests — all must pass**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/components/__tests__/ProjectSettingsPanel.test.tsx 2>&1 | head -40
```

Expected: 8 PASSed.

- [ ] **Step 5: Run all frontend tests — all must pass**

```bash
cd EvoScientist/pm/frontend && npx vitest run 2>&1 | tail -20
```

Expected: all 48 tests pass.

- [ ] **Step 6: Commit**

```bash
git add EvoScientist/pm/frontend/src/components/ProjectSettingsPanel.tsx EvoScientist/pm/frontend/src/components/__tests__/ProjectSettingsPanel.test.tsx
git commit -m "feat(pm): add ProjectSettingsPanel with project edit, delete, and member management"
```

---

## Task 5: Board.tsx — owner check + settings button + panel integration

**Files:**
- Modify: `EvoScientist/pm/frontend/src/pages/Board.tsx`
- Modify: `EvoScientist/pm/frontend/src/pages/__tests__/Board.test.tsx`

- [ ] **Step 1: Write the failing tests**

Read `EvoScientist/pm/frontend/src/pages/__tests__/Board.test.tsx`. Add these 2 tests at the end of the describe block:

```tsx
// Add to the top-level mock setup (needs useAuth mock):
vi.mock('../../auth', () => ({
  useAuth: vi.fn(() => ({ username: 'dr_chen', isAdmin: false, token: 'tok', login: vi.fn(), logout: vi.fn() })),
}))

// Add these 2 tests inside the describe block:
test('renders ⚙ SETTINGS button when user is project owner', () => {
  // MOCK_PROJECT members must include dr_chen as owner
  // Ensure MOCK_PROJECT in Board.test.tsx has: { user_id: 'u1', username: 'dr_chen', role: 'owner', added_at: '...' }
  // mockedUseQuery for project must return MOCK_PROJECT (already set up in beforeEach)
  render(<Board />)
  expect(screen.getByRole('button', { name: /settings/i })).toBeInTheDocument()
})

test('hides ⚙ SETTINGS button when user is not an owner', () => {
  const { mocked } = await import('vitest')
  vi.mocked(useAuth).mockReturnValueOnce({ username: 'lab_tech', isAdmin: false, token: 'tok', login: vi.fn(), logout: vi.fn() })
  // lab_tech is 'editor' in MOCK_PROJECT — not owner
  render(<Board />)
  expect(screen.queryByRole('button', { name: /settings/i })).not.toBeInTheDocument()
})
```

**Note:** Before writing the tests, read the current Board.test.tsx to see the exact structure of `MOCK_PROJECT` and the `beforeEach` mock setup. Integrate the `useAuth` mock and new tests without breaking existing ones. The `MOCK_PROJECT` in the test file must include `members` with `dr_chen` as owner and `lab_tech` as editor.

- [ ] **Step 2: Run the failing tests**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/pages/__tests__/Board.test.tsx 2>&1 | head -40
```

Expected: the 2 new tests FAIL — "Unable to find role button settings".

- [ ] **Step 3: Update `Board.tsx`**

Read `EvoScientist/pm/frontend/src/pages/Board.tsx` first. Then make these changes:

1. Add imports at the top (after existing imports):
```tsx
import { useAuth } from '../auth'
import { ProjectSettingsPanel } from '../components/ProjectSettingsPanel'
```

2. Add state variables inside the `Board` function (near the existing state declarations):
```tsx
const [settingsPanelOpen, setSettingsPanelOpen] = useState(false)
```

3. Add `useAuth` call inside the `Board` function (after `useParams` / `useNavigate`):
```tsx
const { username } = useAuth()
```

4. Add `isOwner` derived value (after `project` data is queried):
```tsx
const isOwner = project?.members.some(m => m.username === username && m.role === 'owner') ?? false
```

5. In the Board header (inside the `marginLeft: 'auto'` div that currently shows member avatars), add the settings button **before** the avatars:
```tsx
{isOwner && (
  <button
    onClick={() => setSettingsPanelOpen(true)}
    style={{
      cursor: 'pointer',
      background: 'rgba(100,140,200,0.07)',
      border: '1px solid rgba(100,140,200,0.14)',
      borderRadius: 5, color: '#64748b',
      padding: '3px 10px', fontSize: 10, fontWeight: 700,
      letterSpacing: '0.06em', fontFamily: 'var(--font-mono)',
      transition: 'color 0.15s, border-color 0.15s',
    }}
    onMouseEnter={e => { e.currentTarget.style.color = '#22d3ee'; e.currentTarget.style.borderColor = 'rgba(34,211,238,0.3)' }}
    onMouseLeave={e => { e.currentTarget.style.color = '#64748b'; e.currentTarget.style.borderColor = 'rgba(100,140,200,0.14)' }}
  >⚙ SETTINGS</button>
)}
```

6. Below the `{editingTask && editAnchorRect && ...}` block, add the settings panel render:
```tsx
{settingsPanelOpen && project && (
  <ProjectSettingsPanel
    project={project}
    projectId={projectId!}
    onClose={() => setSettingsPanelOpen(false)}
  />
)}
```

- [ ] **Step 4: Run all frontend tests — all must pass**

```bash
cd EvoScientist/pm/frontend && npx vitest run 2>&1 | tail -25
```

Expected: all 50 tests pass (48 existing + 2 new Board tests).

- [ ] **Step 5: TypeScript check — no errors**

```bash
cd EvoScientist/pm/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 6: Production build — succeeds**

```bash
cd EvoScientist/pm/frontend && npm run build 2>&1 | tail -15
```

Expected: build succeeds, no errors.

- [ ] **Step 7: Full backend test suite — no regressions**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist && uv run pytest tests/pm/ -q --timeout=30 2>&1 | tail -10
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add EvoScientist/pm/frontend/src/pages/Board.tsx EvoScientist/pm/frontend/src/pages/__tests__/Board.test.tsx
git commit -m "feat(pm): add owner-only Settings button and ProjectSettingsPanel to Board"
```

---

## Self-Review

**Spec coverage check:**
- ✅ `GET /users/search` backend endpoint — Task 1
- ✅ `UserSearchResult` schema — Task 1
- ✅ `searchUsers`, `updateProject`, `deleteProject`, `removeMember`, `updateMemberRole` in `api.ts` — Task 2
- ✅ Description textarea in create-project form — Task 3
- ✅ `ProjectSettingsPanel` with project edit (name, description) + SAVE — Task 4
- ✅ DELETE PROJECT with 3s two-click confirm + navigate to `/projects` — Task 4
- ✅ Member list with role badges, role change, remove (disabled for self) — Task 4
- ✅ ADD RESEARCHER with 300ms debounce search, dropdown, role select, ADD button — Task 4
- ✅ Error handling on save and add member — Task 4
- ✅ Owner-only ⚙ SETTINGS button in Board header — Task 5
- ✅ `settingsPanelOpen` state + `ProjectSettingsPanel` rendered in Board — Task 5
- ✅ Role visibility: editors/viewers see no Settings button — Task 5 (tested)

**Type consistency check:**
- `ProjectSettingsPanel` props: `project: Project, projectId: string, onClose: () => void` — used consistently in Task 4 (component) and Task 5 (Board call site)
- `api.updateProject(id: string, data: {name?, description?})` — defined in Task 2, called in Task 4
- `api.deleteProject(id: string)` — defined in Task 2, called in Task 4
- `api.removeMember(projectId: string, userId: string)` — defined in Task 2, called in Task 4
- `api.updateMemberRole(projectId: string, userId: string, role: string)` — defined in Task 2, called in Task 4
- `api.searchUsers(q: string)` — defined in Task 2, called in Task 4
- `search_users` CRUD — defined in Task 1, imported in Task 1 route

**Placeholder scan:** No TBD/TODO patterns. All code blocks are complete.
