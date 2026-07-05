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
    data: { prompt: string; agent_type?: string; target_field?: string | null }
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

  // ── Admissions ────────────────────────────────────────────────────────────
  listAdmissions: (status?: string) => {
    const qs = status ? `?status=${encodeURIComponent(status)}` : ''
    return request<Admission[]>('GET', `/admissions${qs}`)
  },
  getAdmission: (id: string) =>
    request<Admission>('GET', `/admissions/${id}`),
  importAdmissions: (file: File): Promise<AdmissionImportResponse> => {
    const token = getToken()
    const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {}
    const form = new FormData()
    form.append('file', file)
    return fetch(`${BASE}/admissions/import`, {
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
      return resp.json() as Promise<AdmissionImportResponse>
    })
  },
  updateAdmission: (id: string, data: { reviewer_id?: string | null; review_notes?: string | null }) =>
    request<Admission>('PATCH', `/admissions/${id}`, data),
  acceptAdmission: (id: string, notes?: string) =>
    request<Admission>('POST', `/admissions/${id}/accept`, { notes }),
  rejectAdmission: (id: string, notes: string) =>
    request<Admission>('POST', `/admissions/${id}/reject`, { notes }),
  deleteAdmission: (admissionId: string) =>
    request<void>('DELETE', `/admissions/${admissionId}`),

  grantAid: (admissionId: string, data: { aid_percentage: number; notes?: string | null }) =>
    request<Admission>('POST', `/admissions/${admissionId}/financial-aid`, data),
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
export interface Lab {
  id: string; name: string; pi_id: string | null
  department: string; university: string
  created_at: string; updated_at: string
  members: LabMember_[]
}
export interface LabMember_ { user_id: string; username: string; role: string; joined_at: string }
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

  // ── Labs ─────────────────────────────────────────────────────────────────────
  listLabs: () => request<Lab[]>('GET', '/labs'),
  getLab: (id: string) => request<Lab>('GET', `/labs/${id}`),
  createLab: (name: string, department?: string, university?: string) =>
    request<Lab>('POST', '/labs', { name, department, university }),
  updateLab: (id: string, data: { name?: string; pi_id?: string | null; department?: string; university?: string }) =>
    request<Lab>('PUT', `/labs/${id}`, data),
  deleteLab: (id: string) => request<void>('DELETE', `/labs/${id}`),
  addLabMember: (labId: string, userId: string, role: string) =>
    request<LabMember_>('POST', `/labs/${labId}/members`, { user_id: userId, role }),
  removeLabMember: (labId: string, userId: string) =>
    request<void>('DELETE', `/labs/${labId}/members/${userId}`),

  // ── Publications ──────────────────────────────────────────────────────────
  listPublications: (projectId?: string, status?: string) => {
    const params = new URLSearchParams()
    if (projectId) params.set('project_id', projectId)
    if (status) params.set('status', status)
    const qs = params.toString()
    return request<Publication_[]>('GET', `/publications${qs ? `?${qs}` : ''}`)
  },
  getPublication: (id: string) => request<Publication_>('GET', `/publications/${id}`),
  createPublication: (data: {
    title: string; project_id?: string | null; venue?: string; venue_type?: string;
    authors?: { name?: string; email?: string }[]; abstract?: string; doi?: string; url?: string
  }) => request<Publication_>('POST', '/publications', data),
  updatePublication: (id: string, data: Partial<{
    title: string; venue: string; venue_type: string; authors: { name?: string; email?: string }[];
    abstract: string; doi: string; url: string; status: string
  }>) => request<Publication_>('PUT', `/publications/${id}`, data),
  submitPublication: (id: string) => request<Publication_>('POST', `/publications/${id}/submit`),
  deletePublication: (id: string) => request<void>('DELETE', `/publications/${id}`),
  listVersions: (pubId: string) => request<Version[]>('GET', `/publications/${pubId}/versions`),
  createVersion: (pubId: string, notes?: string) =>
    request<Version>('POST', `/publications/${pubId}/versions`, { notes }),
  listReviews: (pubId: string) => request<Review[]>('GET', `/publications/${pubId}/reviews`),
  createReview: (pubId: string, data: {
    reviewer_name?: string; comments?: string; decision?: string; round?: number
  }) => request<Review>('POST', `/publications/${pubId}/reviews`, data),

  // ── Publication Pipeline ─────────────────────────────────────────────────
  linkExperimentToPub: (pubId: string, experimentId: string, section?: string) =>
    request<Publication_>('POST', `/publications/${pubId}/link-experiment`, { experiment_id: experimentId, section }),
  unlinkExperimentFromPub: (pubId: string, experimentId: string) =>
    request<Publication_>('DELETE', `/publications/${pubId}/link-experiment/${experimentId}`),
  getPublicationPipeline: (pubId: string) => request<Pipeline>('GET', `/publications/${pubId}/pipeline`),

  // ── Drafting ──────────────────────────────────────────────────────────────
  draftPaper: (projectId: string) =>
    request<{ publication_id: string; status: string }>('POST', `/projects/${projectId}/draft-paper`),
  draftSection: (pubId: string, section: string, style: string = 'standard') =>
    request<{ publication_id: string; section: string; style: string; status: string }>(
      'POST', `/publications/${pubId}/draft-section`, { section, style }
    ),
  draftFromExperiment: (projectId: string, experimentId: string, section: string, style: string = 'standard') =>
    request<{ publication_id: string; experiment_id: string; section: string; status: string }>(
      'POST', `/projects/${projectId}/experiments/${experimentId}/draft-to-publication?section=${section}&style=${style}`
    ),
  revisePublication: (pubId: string, instructions: string, text?: string) =>
    request<{ publication_id: string; status: string }>(
      'POST', `/publications/${pubId}/revise`, { text, instructions }
    ),
  respondToReviewers: (pubId: string, reviewerComments: string) =>
    request<{ publication_id: string; status: string }>(
      'POST', `/publications/${pubId}/respond-to-reviewers`, { reviewer_comments: reviewerComments }
    ),

  // ── AI Research Tools ─────────────────────────────────────────────────────
  generateHypothesis: (projectId: string, topic: string, context?: string) =>
    request<{ status: string; message: string }>('POST', `/projects/${projectId}/generate-hypothesis`, { topic, context }),
  researchIdeation: (projectId: string, topic: string, focusArea?: string, count: number = 5) =>
    request<{ status: string; message: string }>('POST', `/projects/${projectId}/research-ideation`, { topic, focus_area: focusArea, count }),
  validateMethodology: (projectId: string, proposedMethods: string) =>
    request<{ status: string; message: string }>('POST', `/projects/${projectId}/validate-methodology`, { proposed_methods: proposedMethods }),
  verifyCitations: (projectId: string, citations: string) =>
    request<{ status: string; message: string }>('POST', `/projects/${projectId}/verify-citations`, { citations }),

  // ── AI Grant Writer ──────────────────────────────────────────────────────
  draftGrantProposal: (projectId: string, grantType: string) =>
    request<{ status: string; publication_id: string }>('POST', `/projects/${projectId}/grant-proposal`, { grant_type: grantType }),

  // ── Auto Figures ──────────────────────────────────────────────────────────
  generateFigures: (projectId: string, expId: string) =>
    request<{ status: string; experiment_id: string }>('POST', `/projects/${projectId}/experiments/${expId}/generate-figures`),

  // ── Research Impact ───────────────────────────────────────────────────────
  labResearchImpact: (labId: string) =>
    request<LabImpact>('GET', `/labs/${labId}/research-impact`),

  // ── Grants ────────────────────────────────────────────────────────────────
  listGrants: (labId?: string, status?: string, offset = 0, limit = 50) => {
    const p = new URLSearchParams()
    if (labId) p.set('lab_id', labId)
    if (status) p.set('status', status)
    p.set('offset', String(offset)); p.set('limit', String(limit))
    return request<Grant_[]>('GET', `/grants?${p}`)
  },
  createGrant: (data: Record<string, unknown>) => request('POST', '/grants', data),
  getGrant: (id: string) => request<Grant_>('GET', `/grants/${id}`),
  updateGrant: (id: string, data: Record<string, unknown>) => request('PUT', `/grants/${id}`, data),
  deleteGrant: (id: string) => request<void>('DELETE', `/grants/${id}`),

  // ── Conferences ─────────────────────────────────────────────────────────
  listConferences: (projectId?: string, status?: string) => {
    const p = new URLSearchParams()
    if (projectId) p.set('project_id', projectId)
    if (status) p.set('status', status)
    return request<Conference_[]>('GET', `/conferences?${p}`)
  },
  createConference: (data: Record<string, unknown>) => request('POST', '/conferences', data),
  getConference: (id: string) => request<Conference_>('GET', `/conferences/${id}`),
  updateConference: (id: string, data: Record<string, unknown>) => request('PUT', `/conferences/${id}`, data),

  // ── IRB ──────────────────────────────────────────────────────────────────
  listIrbs: (projectId?: string, status?: string) => {
    const p = new URLSearchParams()
    if (projectId) p.set('project_id', projectId)
    if (status) p.set('status', status)
    return request<IRB_[]>('GET', `/irb?${p}`)
  },
  createIrb: (data: Record<string, unknown>) => request('POST', '/irb', data),
  getIrb: (id: string) => request<IRB_>('GET', `/irb/${id}`),
  updateIrb: (id: string, data: Record<string, unknown>) => request('PUT', `/irb/${id}`, data),

  // ── Wiki ─────────────────────────────────────────────────────────────────
  listWikiPages: (labId: string) => request<WikiPage_[]>('GET', `/labs/${labId}/wiki`),
  createWikiPage: (labId: string, data: { title: string; content?: string; tags?: string[] }) =>
    request('POST', `/labs/${labId}/wiki`, data),
  getWikiPage: (labId: string, pageId: string) => request<WikiPage_>('GET', `/labs/${labId}/wiki/${pageId}`),
  updateWikiPage: (labId: string, pageId: string, data: { content?: string; title?: string; tags?: string[] }) =>
    request('PUT', `/labs/${labId}/wiki/${pageId}`, data),

  // ── Global Search ────────────────────────────────────────────────────────
  globalSearch: (q: string) => request<SearchResults>('GET', `/search?q=${encodeURIComponent(q)}`),

  // ── Templates ──────────────────────────────────────────────────────────────
  listTemplates: () => request<Template[]>('GET', '/templates'),
  getTemplate: (id: string) => request<Template>('GET', `/templates/${id}`),
  createProjectFromTemplate: (data: { template_id: string; name: string; description?: string; lab_id?: string }) =>
    request<Project>('POST', '/templates/from-template', data),

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

export interface Admission {
  id: string
  form_submission_id: number | null
  applicant_name: string
  supervisor: string | null
  email: string
  phone: string | null
  university: string | null
  department: string | null
  service_areas: string
  modas_members: string
  grant_context: string | null
  comments: string | null
  status: 'submitted' | 'reviewing' | 'accepted' | 'rejected'
  reviewer_id: string | null
  review_notes: string | null
  reviewed_at: string | null
  created_project_id: string | null
  aid_percentage: number | null
  aid_notes: string | null
  aid_at: string | null
  imported_at: string
  created_at: string
  updated_at: string
}

export interface AdmissionImportResponse {
  imported: number
  skipped: number
  admission_ids: string[]
}

export interface Publication_ {
  id: string; project_id: string | null; title: string; venue: string | null
  venue_type: string; authors: { name?: string; email?: string }[]; status: string
  doi: string | null; url: string | null; abstract: string | null
  submitted_at: string | null; accepted_at: string | null; published_at: string | null
  created_by: string; created_at: string; updated_at: string
}
export interface Version {
  id: string; publication_id: string; version: number
  file_path: string | null; notes: string | null; created_by: string; created_at: string
}
export interface Review {
  id: string; publication_id: string; reviewer_name: string | null
  comments: string | null; decision: string | null; round: number; created_at: string
}

export interface LabImpact {
  lab_id: string; lab_name: string; total_publications: number
  s2_matched: number; total_citations: number; h_index: number
  average_citations_per_paper: number; member_count: number
  publications_by_status: Record<string, number>
  publications: { title: string; status: string; citations: number; influential_citations: number; venue: string; year: number; fields: string[]; is_open_access: boolean }[]
  members: { user_id: string; role: string }[]
}

export interface Pipeline {
  publication_id: string; title: string; status: string
  project: { id: string; name: string; description: string } | null
  linked_experiments: { experiment_id: string; name: string; status: string; hypothesis: string | null; section: string | null; entry_count: number }[]
  pipeline_stages: { stage: string; status: string; name?: string; id?: string; date?: string; count?: number; reviews?: number }[]
}

export interface Grant_ { id: string; title: string; funder: string; amount_awarded: number | null; currency: string; status: string; submitted_at: string | null; start_date: string | null; end_date: string | null; project_id: string | null; lab_id: string | null; created_at: string }
export interface Conference_ { id: string; name: string; venue: string | null; deadline: string | null; status: string; presentation_type: string; decision_date: string | null }
export interface IRB_ { id: string; title: string; institution: string; protocol_number: string; status: string; approval_date: string | null; expiry_date: string | null }
export interface WikiPage_ { id: string; title: string; slug: string; content?: string; tags?: string[]; updated_at: string }
export interface SearchResults { projects: { id: string; name: string; type: string }[]; tasks: { id: string; title: string; project_id: string; type: string }[]; experiments: { id: string; name: string; project_id: string; type: string }[]; publications: { id: string; title: string; type: string }[] }

export interface Template {
  id: string; name: string; description: string; domain: string; icon: string
  phases: { name: string; color: string; position: number }[]
  experiment_types: { name: string; description: string }[]
  tasks: { title: string; description: string; phase: string; priority: string }[]
}
