const BASE = '/api/v1'

function getToken(): string | null {
  return sessionStorage.getItem('pm_token')
}

function authHeaders(): HeadersInit {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    method,
    headers: authHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (resp.status === 401) {
    sessionStorage.removeItem('pm_token')
    window.location.href = '/login'
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? resp.statusText)
  }
  if (resp.status === 204) return undefined as T
  return resp.json() as Promise<T>
}

export const api = {
  login: (username: string, password: string) =>
    request<{ token: string; user_id: string; username: string; is_admin: boolean }>(
      'POST', '/auth/login', { username, password }
    ),
  me: () => request<{ id: string; username: string; is_admin: boolean }>('GET', '/users/me'),
  setupStatus: () => request<{ needs_setup: boolean }>('GET', '/users/setup/status'),
  listUsers: () => request<UserRecord[]>('GET', '/users'),
  createUser: (username: string, password: string, email?: string) =>
    request<UserRecord>('POST', '/users', { username, password, email }),
  deleteUser: (userId: string) => request<void>('DELETE', `/users/${userId}`),
  createAdmin: (username: string, password: string, email?: string) =>
    request<{ id: string; username: string }>('POST', '/users/setup/admin', { username, password, email }),
  listProjects: () => request<Project[]>('GET', '/projects'),
  createProject: (name: string, description?: string) => request<Project>('POST', '/projects', { name, description }),
  getProject: (id: string) => request<Project>('GET', `/projects/${id}`),
  addMember: (projectId: string, userId: string, role: string) =>
    request('POST', `/projects/${projectId}/members`, { user_id: userId, role }),
  searchUsers: (q: string) =>
    request<{ id: string; username: string }[]>('GET', `/users/search?q=${encodeURIComponent(q)}`),
  updateProject: (id: string, data: { name?: string; description?: string | null }) =>
    request<Project>('PUT', `/projects/${id}`, data),
  deleteProject: (id: string) =>
    request<void>('DELETE', `/projects/${id}`),
  removeMember: (projectId: string, userId: string) =>
    request<void>('DELETE', `/projects/${projectId}/members/${userId}`),
  updateMemberRole: (projectId: string, userId: string, role: string) =>
    request<Member>('PUT', `/projects/${projectId}/members/${userId}`, { role }),
  listTasks: (projectId: string) => request<Task[]>('GET', `/projects/${projectId}/tasks`),
  createTask: (projectId: string, data: Partial<Task>) => request<Task>('POST', `/projects/${projectId}/tasks`, data),
  updateTask: (projectId: string, taskId: string, data: Partial<Task>) =>
    request<Task>('PUT', `/projects/${projectId}/tasks/${taskId}`, data),
  deleteTask: (projectId: string, taskId: string) =>
    request<void>('DELETE', `/projects/${projectId}/tasks/${taskId}`),
  listComments: (projectId: string, taskId: string) =>
    request<Comment[]>('GET', `/projects/${projectId}/tasks/${taskId}/comments`),
  addComment: (projectId: string, taskId: string, body: string) =>
    request<Comment>('POST', `/projects/${projectId}/tasks/${taskId}/comments`, { body }),
  createRun: (projectId: string, taskId: string, data: { agent_type: string; prompt: string }) =>
    request<Run>('POST', `/projects/${projectId}/tasks/${taskId}/runs`, data),
  listRuns: (projectId: string, taskId: string) =>
    request<Run[]>('GET', `/projects/${projectId}/tasks/${taskId}/runs`),
  cancelRun: (runId: string) =>
    request<void>('DELETE', `/runs/${runId}`),
  streamRunUrl: (runId: string): string => `/api/v1/runs/${runId}/stream`,
  // ── Experiments ──────────────────────────────────────────────────────────
  listExperiments: (projectId: string) =>
    request<Experiment[]>('GET', `/projects/${projectId}/experiments`),
  createExperiment: (projectId: string, data: {
    name: string; hypothesis?: string | null; protocol?: string | null;
    status?: string; tags?: string[]; deadline?: string | null
  }) => request<Experiment>('POST', `/projects/${projectId}/experiments`, data),
  getExperiment: (projectId: string, expId: string) =>
    request<Experiment>('GET', `/projects/${projectId}/experiments/${expId}`),
  updateExperiment: (projectId: string, expId: string, data: {
    name?: string; hypothesis?: string | null; protocol?: string | null;
    status?: string; tags?: string[]; deadline?: string | null
  }) => request<Experiment>('PATCH', `/projects/${projectId}/experiments/${expId}`, data),
  deleteExperiment: (projectId: string, expId: string) =>
    request<void>('DELETE', `/projects/${projectId}/experiments/${expId}`),
  linkTask: (projectId: string, expId: string, taskId: string) =>
    request<{ experiment_id: string; task_id: string }>(
      'POST', `/projects/${projectId}/experiments/${expId}/tasks`, { task_id: taskId }
    ),
  unlinkTask: (projectId: string, expId: string, taskId: string) =>
    request<void>('DELETE', `/projects/${projectId}/experiments/${expId}/tasks/${taskId}`),
  listLinkedTasks: (projectId: string, expId: string) =>
    request<Task[]>('GET', `/projects/${projectId}/experiments/${expId}/tasks`),
  listEntries: (projectId: string, expId: string, type?: 'note' | 'result') =>
    request<ExperimentEntry[]>(
      'GET', `/projects/${projectId}/experiments/${expId}/entries${type ? `?type=${type}` : ''}`
    ),
  createEntry: (projectId: string, expId: string, data: { type: 'note' | 'result'; title: string; body?: string }) =>
    request<ExperimentEntry>('POST', `/projects/${projectId}/experiments/${expId}/entries`, data),
  updateEntry: (projectId: string, expId: string, entryId: string, data: { title?: string; body?: string }) =>
    request<ExperimentEntry>('PATCH', `/projects/${projectId}/experiments/${expId}/entries/${entryId}`, data),
  deleteEntry: (projectId: string, expId: string, entryId: string) =>
    request<void>('DELETE', `/projects/${projectId}/experiments/${expId}/entries/${entryId}`),
  // ── Assists ──────────────────────────────────────────────────────────────
  createAssist: (
    projectId: string,
    expId: string,
    data: { prompt: string; target_field?: string | null }
  ) => request<Assist>('POST', `/projects/${projectId}/experiments/${expId}/assist`, data),
  listAssists: (projectId: string, expId: string) =>
    request<Assist[]>('GET', `/projects/${projectId}/experiments/${expId}/assists`),
  cancelAssist: (assistId: string) =>
    request<void>('DELETE', `/assists/${assistId}`),
  assistStreamUrl: (assistId: string): string =>
    `/api/v1/assists/${assistId}/stream`,
  // ── Attachments ───────────────────────────────────────────────────────────
  listAttachments: (projectId: string, expId: string, entryId: string) =>
    request<Attachment[]>('GET', `/projects/${projectId}/experiments/${expId}/entries/${entryId}/attachments`),
  uploadAttachment: (projectId: string, expId: string, entryId: string, file: File): Promise<Attachment> => {
    const token = getToken()
    const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {}
    const form = new FormData()
    form.append('file', file)
    return fetch(`${BASE}/projects/${projectId}/experiments/${expId}/entries/${entryId}/attachments`, {
      method: 'POST',
      headers,
      body: form,
    }).then(async resp => {
      if (resp.status === 401) {
        sessionStorage.removeItem('pm_token')
        window.location.href = '/login'
      }
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }))
        throw new Error(err.detail ?? resp.statusText)
      }
      return resp.json() as Promise<Attachment>
    })
  },
  deleteAttachment: (attachmentId: string) =>
    request<void>('DELETE', `/attachments/${attachmentId}`),
}

export interface UserRecord {
  id: string; username: string; email: string | null; is_admin: boolean; created_at: string
}

export interface Project {
  id: string; name: string; description: string | null
  created_by: string; created_at: string; archived_at: string | null
  members: Member[]
}
export interface Member { user_id: string; username: string; role: string; added_at: string }
export interface Task {
  id: string; project_id: string; title: string; description: string | null
  assignee_id: string | null; status: 'todo' | 'in_progress' | 'done'
  priority: 'high' | 'medium' | 'low'; deadline: string | null
  session_id: string | null; created_by: string; created_at: string; updated_at: string
  phase_id?: string | null
  blocked_by?: string[]
}
export interface Comment { id: string; task_id: string; author_id: string | null; body: string; created_at: string }
export interface Run {
  id: string
  task_id: string
  project_id: string
  agent_type: 'research' | 'code' | 'data_analysis' | 'writing'
  prompt: string
  status: 'pending' | 'running' | 'done' | 'failed' | 'cancelled'
  output: string | null
  error: string | null
  started_at: string | null
  finished_at: string | null
  created_by: string
  created_at: string
}

export interface Experiment {
  id: string
  project_id: string
  name: string
  hypothesis: string | null
  protocol: string | null
  status: 'planned' | 'running' | 'completed'
  tags: string[]
  deadline: string | null
  phase_id?: string | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface ExperimentEntry {
  id: string
  experiment_id: string
  type: 'note' | 'result'
  title: string
  body: string
  author_id: string | null
  created_at: string
  updated_at: string
}

export interface Assist {
  id: string
  experiment_id: string
  project_id: string
  prompt: string
  status: 'pending' | 'running' | 'done' | 'failed' | 'cancelled'
  output: string | null
  error: string | null
  target_field: 'hypothesis' | 'protocol' | 'entry_body' | null
  created_by: string
  created_at: string
  finished_at: string | null
}

export interface ProjectPhase {
  id: string
  project_id: string
  name: string
  color: string
  position: number
  target_date: string | null
  created_by: string
  created_at: string
}

export interface TaskDependency {
  task_id: string
  depends_on_id: string
  dep_type: 'hard' | 'soft'
  created_by: string
  created_at: string
}

export interface DependenciesListResponse {
  dependencies: TaskDependency[]
  dependents: TaskDependency[]
}

// ── Phases ────────────────────────────────────────────────────────────────────

export async function listPhases(projectId: string, token: string): Promise<ProjectPhase[]> {
  const resp = await fetch(`${BASE}/projects/${projectId}/phases`, {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  })
  if (resp.status === 401) {
    sessionStorage.removeItem('pm_token')
    window.location.href = '/login'
    throw new Error('Session expired')
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? resp.statusText)
  }
  return resp.json() as Promise<ProjectPhase[]>
}

export async function createPhase(
  projectId: string,
  data: { name: string; color?: string; position?: number; target_date?: string | null },
  token: string,
): Promise<ProjectPhase> {
  const resp = await fetch(`${BASE}/projects/${projectId}/phases`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (resp.status === 401) {
    sessionStorage.removeItem('pm_token')
    window.location.href = '/login'
    throw new Error('Session expired')
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? resp.statusText)
  }
  return resp.json() as Promise<ProjectPhase>
}

export async function updatePhase(
  projectId: string,
  phaseId: string,
  data: Partial<{ name: string; color: string; position: number; target_date: string | null }>,
  token: string,
): Promise<ProjectPhase> {
  const resp = await fetch(`${BASE}/projects/${projectId}/phases/${phaseId}`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (resp.status === 401) {
    sessionStorage.removeItem('pm_token')
    window.location.href = '/login'
    throw new Error('Session expired')
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? resp.statusText)
  }
  return resp.json() as Promise<ProjectPhase>
}

export async function deletePhase(projectId: string, phaseId: string, token: string): Promise<void> {
  const resp = await fetch(`${BASE}/projects/${projectId}/phases/${phaseId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  })
  if (resp.status === 401) {
    sessionStorage.removeItem('pm_token')
    window.location.href = '/login'
    return
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? resp.statusText)
  }
  // 204 No Content — no body to parse
}

export async function assignTaskPhase(
  projectId: string,
  phaseId: string,
  taskId: string,
  token: string,
): Promise<void> {
  const resp = await fetch(`${BASE}/projects/${projectId}/phases/${phaseId}/assign-task`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: taskId }),
  })
  if (resp.status === 401) {
    sessionStorage.removeItem('pm_token')
    window.location.href = '/login'
    return
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? resp.statusText)
  }
}

// ── Dependencies ──────────────────────────────────────────────────────────────

export async function listTaskDependencies(
  projectId: string,
  taskId: string,
  token: string,
): Promise<DependenciesListResponse> {
  const resp = await fetch(`${BASE}/projects/${projectId}/tasks/${taskId}/dependencies`, {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  })
  if (resp.status === 401) {
    sessionStorage.removeItem('pm_token')
    window.location.href = '/login'
    throw new Error('Session expired')
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? resp.statusText)
  }
  return resp.json() as Promise<DependenciesListResponse>
}

export async function addTaskDependency(
  projectId: string,
  taskId: string,
  dependsOnId: string,
  depType: 'hard' | 'soft',
  token: string,
): Promise<TaskDependency> {
  const resp = await fetch(`${BASE}/projects/${projectId}/tasks/${taskId}/dependencies`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ depends_on_id: dependsOnId, dep_type: depType }),
  })
  if (resp.status === 401) {
    sessionStorage.removeItem('pm_token')
    window.location.href = '/login'
    throw new Error('Session expired')
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? resp.statusText)
  }
  return resp.json() as Promise<TaskDependency>
}

export async function removeTaskDependency(
  projectId: string,
  taskId: string,
  dependsOnId: string,
  token: string,
): Promise<void> {
  const resp = await fetch(`${BASE}/projects/${projectId}/tasks/${taskId}/dependencies/${dependsOnId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  })
  if (resp.status === 401) {
    sessionStorage.removeItem('pm_token')
    window.location.href = '/login'
    return
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? resp.statusText)
  }
  // 204 No Content — no body to parse
}

// ── Experiment phase assignment ────────────────────────────────────────────────

export async function assignExperimentPhase(
  projectId: string,
  phaseId: string,
  experimentId: string,
  token: string,
): Promise<void> {
  // TODO: A dedicated experiment-phase assignment endpoint does not yet exist.
  // For now, use the experiment PATCH endpoint to set the phase_id field.
  const resp = await fetch(`${BASE}/projects/${projectId}/experiments/${experimentId}`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ phase_id: phaseId }),
  })
  if (resp.status === 401) {
    sessionStorage.removeItem('pm_token')
    window.location.href = '/login'
    return
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? resp.statusText)
  }
}

export interface Attachment {
  id: string
  entry_id: string
  filename: string
  content_type: string
  size_bytes: number
  uploaded_by: string | null
  created_at: string
  download_url: string
}
