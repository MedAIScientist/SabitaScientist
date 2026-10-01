const BASE = '/api/v1'

function getToken(): string | null {
  return sessionStorage.getItem('pm_token')
}

function authHeaders(): HeadersInit {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
}

export async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  opts?: { skipAuthRedirect?: boolean },
): Promise<T> {
  const hadToken = getToken() !== null
  const resp = await fetch(`${BASE}${path}`, {
    method,
    headers: authHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  // A 401 only means the session expired when we actually sent a token. Without
  // this guard a rejected /auth/login reloaded the page, so the error message
  // never reached the user and the form just appeared to reset.
  if (resp.status === 401 && hadToken && !opts?.skipAuthRedirect) {
    sessionStorage.removeItem('pm_token')
    window.location.href = '/login'
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    const detail = err.detail
    throw new Error(typeof detail === 'string' ? detail : resp.statusText || 'Request failed')
  }
  if (resp.status === 204) return undefined as T
  return resp.json() as Promise<T>
}

export const api = {
  login: (username: string, password: string) =>
    request<{ token: string; user_id: string; username: string; is_admin: boolean; role: string }>(
      'POST', '/auth/login', { username, password }, { skipAuthRedirect: true }
    ),
  me: () => request<{ id: string; username: string; is_admin: boolean; role: string }>('GET', '/users/me'),
  setPassword: (newPassword: string) =>
    request<UserRecord>('PUT', '/users/me', { new_password: newPassword }),
  setupStatus: () => request<{ needs_setup: boolean }>('GET', '/users/setup/status'),
  listUsers: () => request<UserRecord[]>('GET', '/users'),
  createUser: (username: string, password: string, email?: string, role: string = 'student', is_admin: boolean = false) =>
    request<UserRecord>('POST', '/users', { username, password, email, role, is_admin }),
  updateUser: (userId: string, data: { username?: string; email?: string | null; is_admin?: boolean; role?: string }) =>
    request<UserRecord>('PUT', `/users/${userId}`, data),
  deleteUser: (userId: string) => request<void>('DELETE', `/users/${userId}`),
  bulkImportUsers: (rows: { username: string; password: string; email?: string; role?: string }[]) =>
    request<{ created: number; errors: string[] }>('POST', '/users/bulk-import', { rows }),
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
    status?: string; tags?: string[]; deadline?: string | null;
    phase_id?: string | null
  }) => request<Experiment>('POST', `/projects/${projectId}/experiments`, data),
  getExperiment: (projectId: string, expId: string) =>
    request<Experiment>('GET', `/projects/${projectId}/experiments/${expId}`),
  updateExperiment: (projectId: string, expId: string, data: {
    name?: string; hypothesis?: string | null; protocol?: string | null;
    status?: string; tags?: string[]; deadline?: string | null; phase_id?: string | null
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
  listLinkedExperiments: (projectId: string, taskId: string) =>
    request<Experiment[]>('GET', `/projects/${projectId}/tasks/${taskId}/experiments`),
  // ── Experiment data lineage ──────────────────────────────────────────────
  // What the experiment consumed (dataset), how it was processed (de-id run) and
  // what it produced (CVAT annotations, WebKnossos segmentation).
  listExperimentAssets: (projectId: string, expId: string) =>
    request<ExperimentAsset[]>('GET', `/projects/${projectId}/experiments/${expId}/assets`),
  linkExperimentAsset: (
    projectId: string,
    expId: string,
    data: {
      asset_type: ExperimentAssetType; asset_id: string
      role?: ExperimentAssetRole; note?: string | null
    },
  ) => request<ExperimentAsset>(
    'POST', `/projects/${projectId}/experiments/${expId}/assets`, data,
  ),
  unlinkExperimentAsset: (
    projectId: string, expId: string, assetType: string, assetId: string,
  ) => request<void>(
    'DELETE', `/projects/${projectId}/experiments/${expId}/assets/${assetType}/${assetId}`,
  ),
  /** Reverse lineage: every asset claim in the project, for the data view. */
  listProjectAssetLinks: (projectId: string) =>
    request<ProjectAssetLink[]>('GET', `/projects/${projectId}/experiment-assets`),
  // ── Experiment metrics ───────────────────────────────────────────────────
  // These are the numbers paper drafting reads; a results CSV uploaded to an
  // entry is parsed into them server-side, so they exist whether or not the UI
  // ever showed them.
  listExperimentMetrics: (projectId: string, expId: string) =>
    request<ExperimentMetric[]>('GET', `/projects/${projectId}/experiments/${expId}/metrics`),
  createExperimentMetric: (projectId: string, expId: string, data: {
    name: string; value: number; unit?: string | null; split?: string | null
    n?: number | null; stderr?: number | null
  }) => request<ExperimentMetric>(
    'POST', `/projects/${projectId}/experiments/${expId}/metrics`, data,
  ),
  deleteExperimentMetric: (projectId: string, expId: string, metricId: string) =>
    request<void>('DELETE', `/projects/${projectId}/experiments/${expId}/metrics/${metricId}`),
  // ── Data / imaging assets a lineage link can point at ────────────────────
  listDatasets: () => request<DatasetSummary[]>('GET', '/datasets'),
  // ── Imaging-data requests (governance lives in routes/datasets.py) ───────
  requestDataset: (data: {
    name: string; purpose: string; lab_id: string; project_id: string; modality?: string
    accession_list: string[]; irb_ids: string[]; renders: boolean; estimated_bytes?: number
  }) => request<DatasetSummary>('POST', '/datasets', data),
  listDatasetRequests: (projectId: string) =>
    request<DatasetRequest[]>('GET', `/projects/${projectId}/dataset-requests`),
  imagingInbox: () => request<ImagingInboxItem[]>('GET', '/imaging/inbox'),
  piApproveDataset: (id: string) => request<DatasetSummary>('POST', `/datasets/${id}/pi-approve`),
  adminApproveDataset: (id: string, retentionUntil: string) =>
    request<DatasetSummary>('POST', `/datasets/${id}/admin-approve`, { retention_until: retentionUntil }),
  proposeDatasetGrant: (id: string, projectId: string) =>
    request<unknown>('POST', `/datasets/${id}/grants`, { project_id: projectId }),
  approveDatasetGrant: (id: string, grantId: string) =>
    request<unknown>('POST', `/datasets/${id}/grants/${grantId}/approve`),
  listProjectDeidRuns: (projectId: string) =>
    request<PipelineRunSummary[]>('GET', `/projects/${projectId}/deid-pipeline-runs`),
  listProjectCvat: (projectId: string) =>
    request<CvatProjectSummary[]>('GET', `/projects/${projectId}/cvat`),
  listProjectWebknossos: (projectId: string) =>
    request<WebKnossosDatasetSummary[]>('GET', `/projects/${projectId}/webknossos`),
  listProjectSandboxes: (projectId: string) =>
    request<SandboxSummary[]>('GET', `/projects/${projectId}/sandboxes`),
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
    reporting_guideline: string; data_availability: string; code_availability: string
    conflict_of_interest: string; funding_statement: string
  }>) => request<Publication_>('PUT', `/publications/${id}`, data),
  submitPublication: (id: string) => request<Publication_>('POST', `/publications/${id}/submit`),
  deletePublication: (id: string) => request<void>('DELETE', `/publications/${id}`),
  listVersions: (pubId: string) => request<Version[]>('GET', `/publications/${pubId}/versions`),
  getVersion: (pubId: string, versionId: string) =>
    request<Version>('GET', `/publications/${pubId}/versions/${versionId}`),
  createVersion: (pubId: string, notes?: string) =>
    request<Version>('POST', `/publications/${pubId}/versions`, { notes }),
  getAiDisclosure: (pubId: string) =>
    request<AiDisclosure>('GET', `/publications/${pubId}/ai-disclosure`),
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

  // ── Background AI jobs ───────────────────────────────────────────────────
  listAiJobs: (params: { projectId?: string; publicationId?: string } = {}) => {
    const q = new URLSearchParams()
    if (params.projectId) q.set('project_id', params.projectId)
    if (params.publicationId) q.set('publication_id', params.publicationId)
    return request<AiJob[]>('GET', `/ai-jobs${q.toString() ? `?${q}` : ''}`)
  },

  // ── AI Research Tools ─────────────────────────────────────────────────────
  generateHypothesis: (projectId: string, topic: string, context?: string) =>
    request<{ status: string; message: string; job_id: string }>('POST', `/projects/${projectId}/generate-hypothesis`, { topic, context }),
  researchIdeation: (projectId: string, topic: string, focusArea?: string, count: number = 5) =>
    request<{ status: string; message: string; job_id: string }>('POST', `/projects/${projectId}/research-ideation`, { topic, focus_area: focusArea, count }),
  validateMethodology: (projectId: string, proposedMethods: string) =>
    request<{ status: string; message: string; job_id: string }>('POST', `/projects/${projectId}/validate-methodology`, { proposed_methods: proposedMethods }),
  verifyCitations: (projectId: string, citations: string) =>
    request<{ status: string; message: string; job_id: string }>('POST', `/projects/${projectId}/verify-citations`, { citations }),

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
  listGrants: (opts: {
    labId?: string; projectId?: string; status?: string
    q?: string; sort?: string; offset?: number; limit?: number
  } = {}) => {
    const p = new URLSearchParams()
    if (opts.labId) p.set('lab_id', opts.labId)
    if (opts.projectId) p.set('project_id', opts.projectId)
    if (opts.status) p.set('status', opts.status)
    if (opts.q) p.set('q', opts.q)
    if (opts.sort) p.set('sort', opts.sort)
    p.set('offset', String(opts.offset ?? 0)); p.set('limit', String(opts.limit ?? 50))
    return request<Grant_[]>('GET', `/grants?${p}`)
  },
  grantStats: (opts: { labId?: string; projectId?: string } = {}) => {
    const p = new URLSearchParams()
    if (opts.labId) p.set('lab_id', opts.labId)
    if (opts.projectId) p.set('project_id', opts.projectId)
    return request<GrantStats>('GET', `/grants/stats?${p}`)
  },
  createGrant: (data: Record<string, unknown>) => request<Grant_>('POST', '/grants', data),
  getGrant: (id: string) => request<Grant_>('GET', `/grants/${id}`),
  updateGrant: (id: string, data: Record<string, unknown>) => request<Grant_>('PUT', `/grants/${id}`, data),
  deleteGrant: (id: string) => request<void>('DELETE', `/grants/${id}`),

  // ── Grant plan: budget, milestones, team ────────────────────────────────
  listGrantBudget: (gid: string) =>
    request<GrantBudgetItem[]>('GET', `/grants/${gid}/budget`),
  createGrantBudgetItem: (gid: string, data: Record<string, unknown>) =>
    request<GrantBudgetItem>('POST', `/grants/${gid}/budget`, data),
  updateGrantBudgetItem: (gid: string, itemId: string, data: Record<string, unknown>) =>
    request<GrantBudgetItem>('PUT', `/grants/${gid}/budget/${itemId}`, data),
  deleteGrantBudgetItem: (gid: string, itemId: string) =>
    request<void>('DELETE', `/grants/${gid}/budget/${itemId}`),

  listGrantMilestones: (gid: string) =>
    request<GrantMilestone[]>('GET', `/grants/${gid}/milestones`),
  createGrantMilestone: (gid: string, data: Record<string, unknown>) =>
    request<GrantMilestone>('POST', `/grants/${gid}/milestones`, data),
  updateGrantMilestone: (gid: string, mid: string, data: Record<string, unknown>) =>
    request<GrantMilestone>('PUT', `/grants/${gid}/milestones/${mid}`, data),
  deleteGrantMilestone: (gid: string, mid: string) =>
    request<void>('DELETE', `/grants/${gid}/milestones/${mid}`),

  listGrantMembers: (gid: string) =>
    request<GrantMember[]>('GET', `/grants/${gid}/members`),
  addGrantMember: (gid: string, data: Record<string, unknown>) =>
    request<GrantMember>('POST', `/grants/${gid}/members`, data),
  updateGrantMember: (gid: string, memberId: string, data: Record<string, unknown>) =>
    request<GrantMember>('PUT', `/grants/${gid}/members/${memberId}`, data),
  removeGrantMember: (gid: string, memberId: string) =>
    request<void>('DELETE', `/grants/${gid}/members/${memberId}`),

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

  // ── MCP Servers ──────────────────────────────────────────────────────────
  mcpMarketplace: (tag?: string) => {
    const qs = tag ? `?tag=${encodeURIComponent(tag)}` : ''
    return request<MCPMarketplace>('GET', `/mcp/marketplace${qs}`)
  },
  mcpInstalled: () => request<MCPInstalled>('GET', '/mcp/installed'),
  mcpInstall: (name: string) => request<{ status: string; name: string }>('POST', '/mcp/install', { name }),
  mcpRemove: (name: string) => request<void>('DELETE', `/mcp/installed/${encodeURIComponent(name)}`),

  // ── Memory / Observations ────────────────────────────────────────────────
  listObservations: (projectId: string, limit = 50) =>
    request<ObservationsList>('GET', `/memory/observations?project_id=${encodeURIComponent(projectId)}&limit=${limit}`),
  searchObservations: (projectId: string, q: string, limit = 10) =>
    request<ObservationSearchResults>('GET', `/memory/search?project_id=${encodeURIComponent(projectId)}&q=${encodeURIComponent(q)}&limit=${limit}`),
  recordObservation: (projectId: string, title: string, body?: string, tags?: string[]) =>
    request<{ status: string }>('POST', '/memory/observations', { project_id: projectId, title, body, tags }),
  linkObservations: (projectId: string, sourceObservationId: string, targetObservationId: string, reason?: string, relation = 'complements') =>
    request('POST', '/memory/observations/link', { project_id: projectId, source_observation_id: sourceObservationId, target_observation_id: targetObservationId, reason, relation }),

  // ── System Health ────────────────────────────────────────────────────────
  systemHealth: () => request<SystemHealth>('GET', '/system/health'),

  // ── Companion applications (CVAT, Curator, JupyterHub, …) ───────────────
  listIntegrations: () => request<IntegrationStatus[]>('GET', '/integrations'),

  // ── Models ──────────────────────────────────────────────────────────────
  listModels: () => request<ModelsResponse>('GET', '/models'),
  currentModel: () => request<CurrentModel>('GET', '/models/current'),
  selectModel: (model: string, provider?: string) =>
    request<{ status: string; model: string; provider: string | null }>('POST', '/models/select', { model, provider }),

  // ── System Prompt ───────────────────────────────────────────────────────
  systemPrompt: () => request<{ system_prompt: string; length: number }>('GET', '/system-prompt'),

  // ── Cron Schedules ──────────────────────────────────────────────────────
  listSchedules: () => request<ScheduleList>('GET', '/schedules'),
  createSchedule: (name: string, schedule: string, prompt: string, timezone?: string) =>
    request<{ status: string; cron_id: string }>('POST', '/schedules', { name, schedule, prompt, timezone }),
  toggleSchedule: (cronId: string, enabled: boolean) =>
    request<{ status: string; cron_id: string; enabled: boolean }>('POST', `/schedules/${encodeURIComponent(cronId)}/toggle`, { enabled }),
  deleteSchedule: (cronId: string) => request<void>('DELETE', `/schedules/${encodeURIComponent(cronId)}`),
  runScheduleNow: (prompt: string) => request<{ status: string; thread_id: string }>('POST', '/schedules/run-now', { prompt }),

  // ── Global Search ────────────────────────────────────────────────────────
  globalSearch: (q: string) => request<SearchResults>('GET', `/search?q=${encodeURIComponent(q)}`),

  // ── Templates ──────────────────────────────────────────────────────────────
  listTemplates: () => request<Template[]>('GET', '/templates'),
  getTemplate: (id: string) => request<Template>('GET', `/templates/${id}`),
  createProjectFromTemplate: (data: { template_id: string; name: string; description?: string; lab_id?: string }) =>
    request<Project>('POST', '/templates/from-template', data),

  // ── Help ─────────────────────────────────────────────────────────────────
  getHelp: () => request<{ intro: string; sections: { slug: string; title: string; html: string }[]; title: string }>('GET', '/help'),
}

export interface UserRecord {
  id: string; username: string; email: string | null; is_admin: boolean; created_at: string; role: string
}

export interface Project {
  id: string; name: string; description: string | null
  created_by: string; created_at: string; archived_at: string | null
  members: Member[]
  lab_id?: string | null
}
export interface Member { user_id: string; username: string; role: string; added_at: string }
export interface Lab {
  id: string; name: string; pi_id: string | null
  department: string; university: string
  created_at: string; updated_at: string
  // Empty unless the caller is a member of this lab or a platform admin — use
  // member_count for the size, which is always the real one.
  members: LabMember_[]
  member_count: number
  can_manage: boolean
}
export interface LabMember_ { user_id: string; username: string; role: string; joined_at: string }
export interface Task {
  id: string; project_id: string; title: string; description: string | null
  assignee_id: string | null; status: 'todo' | 'in_progress' | 'done'
  priority: 'high' | 'medium' | 'low'; deadline: string | null
  session_id: string | null; created_by: string; created_at: string; updated_at: string
  phase_id?: string | null
  blocked_by?: string[]
  linked_experiment_count?: number
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
  status: 'planned' | 'running' | 'completed' | 'abandoned'
  tags: string[]
  deadline: string | null
  phase_id?: string | null
  linked_task_count?: number
  linked_asset_count?: number
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

/** Kinds of data/imaging asset an experiment can be traced to. */
export type ExperimentAssetType =
  | 'dataset' | 'pipeline_run' | 'cvat_project' | 'webknossos_dataset' | 'sandbox'

/** What the asset is to the experiment. */
export type ExperimentAssetRole = 'input' | 'processing' | 'output' | 'reference'

export const EXPERIMENT_ASSET_ROLES: ExperimentAssetRole[] = [
  'input', 'processing', 'output', 'reference',
]

export const EXPERIMENT_ASSET_TYPE_LABELS: Record<ExperimentAssetType, string> = {
  dataset: 'IMAGING DATASET',
  pipeline_run: 'DE-ID RUN',
  cvat_project: 'CVAT ANNOTATION',
  webknossos_dataset: 'WEBKNOSSOS SEGMENTATION',
  sandbox: 'SANDBOX',
}

export interface ExperimentAsset {
  experiment_id: string
  asset_type: ExperimentAssetType
  asset_id: string
  role: ExperimentAssetRole
  note: string | null
  linked_at: string
  linked_by: string
  /** Resolved server-side so the UI needs no per-type table knowledge. */
  label: string | null
  detail: string | null
}

export interface ExperimentMetric {
  id: string
  experiment_id: string
  name: string
  value: number
  unit: string | null
  split: string | null
  n: number | null
  stderr: number | null
  source_attachment_id: string | null
  recorded_by: string | null
  created_at: string
}

/** One experiment's claim on one asset. */
export interface ProjectAssetLink {
  experiment_id: string
  experiment_name: string
  asset_type: ExperimentAssetType
  asset_id: string
  role: ExperimentAssetRole
}

export interface DatasetSummary {
  id: string; name: string; modality: string | null; status: string; lab_id: string
  /** Object-storage bucket the cohort is delivered into (set on admin approval). */
  bucket?: string | null
}

export interface PipelineRunSummary {
  id: string; pipeline_id: string; project_id: string
  input_location: string; output_location: string; status: string
  records_processed: number | null; completed_at: string | null
}

export interface CvatProjectSummary {
  id: string; project_id: string; cvat_id: number; name: string
  status: string; num_images: number; num_annotations: number
}

export interface WebKnossosDatasetSummary {
  id: string; project_id: string; name: string; directory_name: string
  status: string; num_skeletons: number; num_volumes: number
}

export interface SandboxSummary {
  id: string; project_id: string; name: string; status: string
  access_url: string | null; expires_at: string | null
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
  id: string; project_id: string | null; project_name?: string | null; title: string; venue: string | null
  venue_type: string; authors: { name?: string; email?: string }[]; status: string
  doi: string | null; url: string | null; abstract: string | null
  submitted_at: string | null; accepted_at: string | null; published_at: string | null
  reporting_guideline: string | null; data_availability: string | null
  code_availability: string | null; conflict_of_interest: string | null
  funding_statement: string | null
  created_by: string; created_at: string; updated_at: string
}
export interface Version {
  id: string; publication_id: string; version: number
  file_path: string | null; notes: string | null; created_by: string; created_at: string
  section: string | null; generated_by: string | null; model: string | null
  prompt_hash: string | null; content_length: number
  content: string | null   // only populated by getVersion
}
export interface AiDisclosure {
  publication_id: string; statement: string
  ai_version_count: number; human_version_count: number
  models_used: string[]; sections: string[]
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

export interface Grant_ {
  id: string; title: string; funder: string
  amount_requested: number | null; amount_awarded: number | null
  currency: string; status: string
  submitted_at: string | null; awarded_at: string | null
  start_date: string | null; end_date: string | null
  description: string | null; pi_id: string | null; pi_username: string | null
  project_id: string | null; lab_id: string | null
  created_by: string; created_at: string; updated_at: string
  can_manage: boolean
}

export type GrantStatus =
  | 'draft' | 'submitted' | 'under_review' | 'awarded'
  | 'rejected' | 'active' | 'closed'

export const GRANT_STATUSES: GrantStatus[] = [
  'draft', 'submitted', 'under_review', 'awarded', 'rejected', 'active', 'closed',
]

export interface GrantCurrencyTotal {
  currency: string; requested: number; awarded: number; count: number
}

export interface GrantStats {
  total: number
  by_status: Record<string, number>
  totals_by_currency: GrantCurrencyTotal[]
  decided: number
  won: number
  success_rate: number | null
  ending_soon: number
  overdue_milestones: number
  open_reports: number
  budget_planned: number
  budget_spent: number
}

export type GrantBudgetCategory =
  | 'personnel' | 'equipment' | 'consumables' | 'travel' | 'services' | 'other'

export const GRANT_BUDGET_CATEGORIES: GrantBudgetCategory[] = [
  'personnel', 'equipment', 'consumables', 'travel', 'services', 'other',
]

export interface GrantBudgetItem {
  id: string; grant_id: string; category: GrantBudgetCategory
  description: string | null
  planned_amount: number; spent_amount: number
  position: number; created_at: string; updated_at: string
}

export type GrantMilestoneKind = 'milestone' | 'report' | 'deliverable'

export const GRANT_MILESTONE_KINDS: GrantMilestoneKind[] = [
  'milestone', 'report', 'deliverable',
]

export interface GrantMilestone {
  id: string; grant_id: string; title: string; kind: GrantMilestoneKind
  due_date: string | null; completed_at: string | null; owner_id: string | null
  notes: string | null; position: number; created_at: string; updated_at: string
}

export type GrantMemberRole = 'pi' | 'co_pi' | 'researcher' | 'assistant' | 'advisor'

export const GRANT_MEMBER_ROLES: GrantMemberRole[] = [
  'pi', 'co_pi', 'researcher', 'assistant', 'advisor',
]

export interface GrantMember {
  id: string; grant_id: string; user_id: string; username: string | null
  role: GrantMemberRole; share_percent: number | null; added_at: string
}
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

// ── MCP ──────────────────────────────────────────────────────────────────────

export interface MCPServerItem {
  name: string; label: string; description: string; tags: string[]
  transport: string; pip_package: string | null; env_key: string | null
  env_hint: string; env_optional: boolean; installed: boolean
}
export interface MCPMarketplace { servers: MCPServerItem[]; tags: string[] }
export interface MCPInstalledServer { name: string; transport: string; command: string | null; args: string[]; url: string | null }
export interface MCPInstalled { servers: MCPInstalledServer[] }

// ── Memory / Observations ────────────────────────────────────────────────────

export interface ObservationItem {
  id: string; title: string; body: string; memory_type: string; scope: string
}
export interface ObservationsList { observations: ObservationItem[]; total: number }
export interface ObservationHit {
  id: string; title: string; body: string; score: number; tags: string[]
}
export interface ObservationSearchResults { results: ObservationHit[] }

// ── System Health ────────────────────────────────────────────────────────────

export interface SystemHealth {
  ai: { runner_model: string; runner_configured: boolean; assistant_model: string; assistant_provider: string | null }
  skills_available: number
}

export type IntegrationKind = 'annotation' | 'imaging' | 'compute' | 'identity'

export interface IntegrationStatus {
  key: string
  name: string
  /** Subpath of this host that the service is published under, e.g. "/cvat/". */
  path: string
  kind: IntegrationKind
  description: string
  up: boolean
  http_status: number | null
  latency_ms: number
}

// ── Models ────────────────────────────────────────────────────────────────────

export interface ModelEntry { short_name: string; model_id: string }
export interface ModelProvider { name: string; models: ModelEntry[] }
export interface ModelsResponse { providers: ModelProvider[]; default_model: string }
export interface CurrentModel { current_model: string | null; current_provider: string | null; default_model: string }

// ── Cron Schedules ────────────────────────────────────────────────────────────

export interface ScheduleItem {
  cron_id: string; name: string; schedule: string; prompt: string
  enabled: boolean; created_at: string; updated_at: string
}
export interface ScheduleList { schedules: ScheduleItem[] }


// ── Academic supervision ────────────────────────────────────────────────────

export interface SupervisorAssignment {
  id: string; student_id: string; professor_id: string
  active_from: string; active_until: string | null; created_at: string
}

export interface WeeklyReportItem {
  id: string; report_id: string
  task_id: string | null; publication_id: string | null; experiment_id: string | null
  item_title: string; item_kind: string | null; progress_pct: number
  status: string | null; blocker: string | null; needs_help: boolean
  what_changed: string | null; next_step: string | null
  risk_level: string; next_deadline: string | null; sort_order: number
}

export interface WeeklyReport {
  id: string; student_id: string; week_start: string
  status: string; review_status: string; risk_level: string
  risk_override: string | null
  accomplished: string | null; next_focus: string | null; support_requested: string | null
  submitted_at: string | null; reviewed_at: string | null; reviewed_by: string | null
  feedback: string | null; created_at: string; updated_at: string
  items: WeeklyReportItem[]
}

export interface Attendance {
  id: string; professor_id: string; student_id: string; week_start: string
  status: string; joined_mode: string | null; note: string | null; recorded_at: string
}

export interface MeetingSetting {
  id: string; professor_id: string; weekday: number
  time_local: string | null; timezone: string | null
  effective_from: string; created_at: string
}

export interface AcademicJourney {
  id: string; student_id: string; level: string; status: string
  programme: string | null; university: string | null; department: string | null
  start_year: number | null; start_date: string | null; expected_end: string | null
  thesis_title: string | null; created_at: string; updated_at: string
}

export interface GraduationRequirement {
  id: string; level: string; title: string; description: string | null
  req_type: string; research_item_type: string | null; min_stage: string | null
  target_value: number; unit: string | null; required: boolean; active: boolean
  created_at: string
}

export const supervisionApi = {
  myStudents: () => request<SupervisorAssignment[]>('GET', '/supervision/my-students'),
  mySupervisor: () => request<SupervisorAssignment | null>('GET', '/supervision/my-supervisor'),
  assignSupervisor: (studentId: string, professorId: string) =>
    request<SupervisorAssignment>('POST', '/supervision/assignments', { student_id: studentId, professor_id: professorId }),
  listAssignments: (professorId?: string) =>
    request<SupervisorAssignment[]>('GET', professorId ? `/supervision/assignments?professor_id=${professorId}` : '/supervision/assignments'),
  setMeetingSetting: (weekday: number, timeLocal?: string, timezone?: string) =>
    request<MeetingSetting>('POST', '/supervision/meeting-settings', { weekday, time_local: timeLocal, timezone }),
  getMeetingSetting: (week?: string, professorId?: string) => {
    const q = new URLSearchParams()
    if (week) q.set('week', week)
    if (professorId) q.set('professor_id', professorId)
    const qs = q.toString()
    return request<MeetingSetting | null>('GET', `/supervision/meeting-settings${qs ? `?${qs}` : ''}`)
  },
  currentWeekReport: (week?: string) => {
    const qs = week ? `?week=${week}` : ''
    return request<WeeklyReport>('POST', `/supervision/weekly/current${qs}`)
  },
  listReports: (params?: { student_id?: string; status?: string; review_status?: string; risk_level?: string; date_from?: string; date_to?: string }) => {
    const q = new URLSearchParams()
    if (params) Object.entries(params).forEach(([k, v]) => { if (v) q.set(k, v) })
    const qs = q.toString()
    return request<WeeklyReport[]>('GET', `/supervision/reports${qs ? `?${qs}` : ''}`)
  },
  getReport: (id: string) => request<WeeklyReport>('GET', `/supervision/reports/${id}`),
  updateSummary: (id: string, data: { accomplished?: string; next_focus?: string; support_requested?: string }) =>
    request<WeeklyReport>('PUT', `/supervision/reports/${id}/summary`, data),
  upsertItem: (id: string, data: Partial<WeeklyReportItem> & { item_title: string; item_id?: string }) =>
    request<WeeklyReportItem>('PUT', `/supervision/reports/${id}/items`, data),
  deleteItem: (reportId: string, itemId: string) =>
    request<void>('DELETE', `/supervision/reports/${reportId}/items/${itemId}`),
  submitReport: (id: string) => request<WeeklyReport>('POST', `/supervision/reports/${id}/submit`),
  reviewReport: (id: string, data: { review_status: string; feedback?: string; risk_override?: string }) =>
    request<WeeklyReport>('POST', `/supervision/reports/${id}/review`, data),
  recordAttendance: (studentId: string, week: string, data: { status: string; joined_mode?: string; note?: string }) =>
    request<Attendance>('POST', `/supervision/attendance?student_id=${studentId}&week=${week}`, data),
  getAttendance: (studentId: string, week: string) =>
    request<Attendance | null>('GET', `/supervision/attendance?student_id=${studentId}&week=${week}`),
  grantExtension: (studentId: string, week: string, data: { new_deadline: string; reason?: string }) =>
    request<{ id: string; new_deadline: string }>('POST', `/supervision/extensions?student_id=${studentId}&week=${week}`, data),
  listJourneys: (studentId?: string) => {
    const qs = studentId ? `?student_id=${studentId}` : ''
    return request<AcademicJourney[]>('GET', `/supervision/journeys${qs}`)
  },
  createJourney: (data: Partial<AcademicJourney> & { level: string }, studentId?: string) => {
    const qs = studentId ? `?student_id=${studentId}` : ''
    return request<AcademicJourney>('POST', `/supervision/journeys${qs}`, data)
  },
  listRequirements: (level?: string) => {
    const qs = level ? `?level=${level}` : ''
    return request<GraduationRequirement[]>('GET', `/supervision/requirements${qs}`)
  },
  createRequirement: (data: Partial<GraduationRequirement> & { level: string; title: string; req_type: string }) =>
    request<GraduationRequirement>('POST', '/supervision/requirements', data),
  archiveRequirement: (id: string) => request<void>('DELETE', `/supervision/requirements/${id}`),
  researchItems: (params?: { student_id?: string; kind?: string }) => {
    const q = new URLSearchParams()
    if (params?.student_id) q.set('student_id', params.student_id)
    if (params?.kind) q.set('kind', params.kind)
    const qs = q.toString()
    return request<{
      id: string; kind: string; title: string; status: string; stage: string
      venue: string | null; owner_id: string; project_id: string | null
      created_at: string; updated_at: string; link_path: string; deadline?: string | null
    }[]>('GET', `/supervision/research-items${qs ? `?${qs}` : ''}`)
  },
  readiness: (studentId?: string) => {
    const qs = studentId ? `?student_id=${studentId}` : ''
    return request<{
      student_id: string; level: string | null; journey_id: string | null
      thesis_title: string | null; readiness_pct: number
      requirements: { id: string; level: string; title: string; req_type: string; target_value: number; unit: string | null; current_value: number; required: boolean; met: boolean }[]
      summary: { publications: number; journal_papers: number; conference_papers: number }
    }>('GET', `/supervision/readiness${qs}`)
  },
  bulkImportUsers: (rows: { username: string; password: string; email?: string; role?: string }[]) =>
    request<{ created: number; errors: string[] }>('POST', '/users/bulk-import', { rows }),
  draftPaperFromItems: (data: {
    title: string; experiment_ids?: string[]; venue_type?: string
    abstract?: string; link_sections?: Record<string, string>
  }) => request<{ publication_id: string; title: string; linked_experiments: string[]; status: string }>(
    'POST', '/supervision/research-items/draft-paper', data
  ),
  linkItemsToPaper: (pubId: string, data: { experiment_ids: string[]; link_sections?: Record<string, string> }) =>
    request<{ publication_id: string; linked_experiments: string[] }>('POST', `/supervision/papers/${pubId}/link-items`, data),
  paperReadiness: (pubId: string) =>
    request<{
      publication_id: string; status: string; readiness_pct: number; ready_to_submit: boolean
      checks: { id: string; label: string; met: boolean; required: boolean; detail: string }[]
      suggested_tools: string[]; ai_versions: number; human_versions: number
    }>('GET', `/supervision/papers/${pubId}/readiness`),
  paperEvidence: (pubId: string) =>
    request<{
      publication_id: string
      linked_experiments: { experiment_id: string; section: string | null; experiment_name: string }[]
      weekly_updates: { id: string; week_start: string; student_id: string; item_title: string; item_kind: string | null; progress_pct: number; status: string | null; what_changed: string | null; next_step: string | null; needs_help: boolean; blocker: string | null; risk_level: string; next_deadline: string | null }[]
      open_questions: { id: string; item_title: string; blocker: string | null; what_changed: string | null }[]
    }>('GET', `/supervision/papers/${pubId}/evidence`),
  professorAnalytics: () => request<{
    students: { student_id: string; username: string; open_reviews: number; help_requests: number; latest_week: string | null; latest_status: string | null; last_attendance: string | null }[]
    kpis: { submitted_this_week: number; needs_review: number; draft_or_missing: number; help_requests: number; high_risk: number; student_count: number }
    weekly_trend: { week: string; submitted: number; on_time: number }[]
    attendance: Record<string, number>
    reports_needing_attention: { report_id: string; student_id: string; username: string; week_start: string; review_status: string; risk: string; support_requested: string | null }[]
    active_deadlines: { item_title: string; next_deadline: string; progress_pct: number; status: string | null; student_id: string; username: string }[]
    work_mix: { kind: string; count: number }[]
  }>('GET', '/supervision/analytics/professor'),
}

// ── AI usage accounting ──────────────────────────────────────────────────────

/** One row of a usage breakdown — a task name or a model name. */
export interface AiUsageBreakdown {
  label: string
  calls: number
  provider_tokens: number
  estimated_tokens: number
}

/**
 * Token totals. `provider_reported` and `estimated` are deliberately separate:
 * the API never sums a measurement with an estimate.
 */
export interface AiUsageSummary {
  window_days: number | null
  calls: number
  tokens: { provider_reported: number; estimated: number; prompt: number; completion: number }
  avg_duration_ms: number | null
  by_task: AiUsageBreakdown[]
  by_model: AiUsageBreakdown[]
}

export interface AiUsageRecord {
  id: string
  task: string
  source: string
  token_source: string
  model: string | null
  user_id: string | null
  project_id: string | null
  publication_id: string | null
  run_id: string | null
  prompt_tokens: number | null
  completion_tokens: number | null
  total_tokens: number | null
  duration_ms: number | null
  created_at: string
}

export interface AiUsageQuery {
  scope?: 'me' | 'user' | 'all'
  user_id?: string
  project_id?: string
  publication_id?: string
  days?: number
}

function _usageQuery(params: AiUsageQuery): string {
  const q = new URLSearchParams()
  if (params.scope) q.set('scope', params.scope)
  if (params.user_id) q.set('user_id', params.user_id)
  if (params.project_id) q.set('project_id', params.project_id)
  if (params.publication_id) q.set('publication_id', params.publication_id)
  if (params.days) q.set('days', String(params.days))
  const qs = q.toString()
  return qs ? `?${qs}` : ''
}

export const aiUsageApi = {
  summary: (params: AiUsageQuery = {}) =>
    request<AiUsageSummary>('GET', `/ai/usage/summary${_usageQuery(params)}`),
  records: (params: AiUsageQuery & { limit?: number } = {}) => {
    const qs = _usageQuery(params)
    const limit = params.limit ? `${qs ? '&' : '?'}limit=${params.limit}` : ''
    return request<{ records: AiUsageRecord[] }>('GET', `/ai/usage/records${qs}${limit}`)
  },
}


/** A background AI job; ``result_path`` is the in-app route of what it produced. */
export interface AiJob {
  id: string
  kind: string
  title: string
  project_id: string | null
  publication_id: string | null
  status: 'running' | 'done' | 'failed'
  result_path: string | null
  error: string | null
  created_at: string
  finished_at: string | null
}


export interface DatasetStep { key: string; label: string; state: 'done' | 'current' | 'todo' }
export interface IrbBrief { id: string; title: string; status: string; expiry_date: string | null }

/** An imaging-data request as the project sees it: metadata and progress only. */
export interface DatasetRequest {
  id: string; name: string; modality: string | null; purpose: string; status: string
  requested_by: string | null; accession_count: number; created_at: string
  steps: DatasetStep[]; waiting_on: string | null; irbs: IrbBrief[]
}

/** A dataset step waiting on the signed-in PI or admin. */
export interface ImagingInboxItem {
  action: 'pi-approve' | 'admin-approve' | 'propose-grant' | 'approve-grant'
  dataset_id: string; dataset_name: string; modality: string | null; purpose: string
  lab_name: string | null; project_id: string | null; project_name: string | null
  requested_by: string | null; accession_count: number; retention_until: string | null
  grant_id: string | null; irbs: IrbBrief[]; blockers: string[]
}
