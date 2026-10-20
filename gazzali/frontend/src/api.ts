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

/** Upload a file as multipart to *path*. Shared by every attachment owner. */
async function uploadFileTo(path: string, file: File): Promise<Attachment> {
  const token = getToken()
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {}
  const form = new FormData()
  form.append('file', file)
  const resp = await fetch(`${BASE}${path}`, { method: 'POST', headers, body: form })
  if (resp.status === 401) {
    sessionStorage.removeItem('pm_token')
    window.location.href = '/login'
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? resp.statusText)
  }
  return resp.json() as Promise<Attachment>
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
  createProject: (name: string, description?: string, labId?: string) =>
    request<Project>('POST', '/projects', { name, description, lab_id: labId || undefined }),
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
  /** Parse a results table; save=false only previews. */
  importMetricsCsv: (projectId: string, expId: string, text: string, save: boolean) =>
    request<{ metrics: { name: string; value: number; unit: string | null; split: string | null; n: number | null; stderr: number | null }[]; saved: number }>(
      'POST', `/projects/${projectId}/experiments/${expId}/metrics/csv`, { text, save }),
  cvatProgress: (projectId: string, cvatId: string) =>
    request<CvatProgress>('GET', `/projects/${projectId}/cvat/${cvatId}/progress`),
  importCvatMetrics: (projectId: string, expId: string, cvatId: string) =>
    request<{ saved: number; summary: { labels: Record<string, number>; frames_annotated: number; frames_total: number } }>(
      'POST', `/projects/${projectId}/experiments/${expId}/cvat/${cvatId}/import-metrics`),
  deleteExperimentMetric: (projectId: string, expId: string, metricId: string) =>
    request<void>('DELETE', `/projects/${projectId}/experiments/${expId}/metrics/${metricId}`),
  // ── Data / imaging assets a lineage link can point at ────────────────────
  listDatasets: () => request<DatasetSummary[]>('GET', '/datasets'),
  // ── Imaging-data requests (governance lives in routes/datasets.py) ───────
  requestDataset: (data: {
    name: string; purpose: string; lab_id: string; project_id: string; modality?: string
    /** The researcher's saved Curator selection; Medai's server fetches its studies from Curator. */
    curator_selection_id: string; irb_ids: string[]; renders: boolean
  }) => request<DatasetSummary>('POST', '/datasets', data),
  listCuratorSelections: () => request<{ selections: CuratorSelection[] }>('GET', '/curator/selections'),
  listDatasetRequests: (projectId: string) =>
    request<DatasetRequest[]>('GET', `/projects/${projectId}/dataset-requests`),
  imagingInbox: () => request<ImagingInboxItem[]>('GET', '/imaging/inbox'),
  listLabDatasets: (labId: string) =>
    request<LabDataset[]>('GET', `/datasets?lab_id=${encodeURIComponent(labId)}`),
  revokeDatasetGrant: (datasetId: string, grantId: string) =>
    request<void>('DELETE', `/datasets/${datasetId}/grants/${grantId}`),
  piApproveDataset: (id: string) => request<DatasetSummary>('POST', `/datasets/${id}/pi-approve`),
  adminApproveDataset: (id: string, retentionUntil: string, estimatedBytes?: number) =>
    request<DatasetSummary>('POST', `/datasets/${id}/admin-approve`, {
      retention_until: retentionUntil,
      ...(estimatedBytes ? { estimated_bytes: estimatedBytes } : {}),
    }),
  raiseDatasetStorage: (id: string, estimatedBytes: number) =>
    request<LabDataset>('POST', `/datasets/${id}/storage`, { estimated_bytes: estimatedBytes }),
  proposeDatasetGrant: (id: string, projectId: string, opts: { annotate?: boolean; task_size?: number } = {}) =>
    request<unknown>('POST', `/datasets/${id}/grants`, { project_id: projectId, ...opts }),
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
  uploadAttachment: (projectId: string, expId: string, entryId: string, file: File) =>
    uploadFileTo(`/projects/${projectId}/experiments/${expId}/entries/${entryId}/attachments`, file),
  /** Every file in the project, with the task or entry each belongs to. */
  listProjectAttachments: (projectId: string, kind?: 'task' | 'entry') =>
    request<ProjectAttachment[]>(
      'GET', `/projects/${projectId}/attachments${kind ? `?kind=${kind}` : ''}`,
    ),
  /** Files attached to a project task. */
  listTaskAttachments: (projectId: string, taskId: string) =>
    request<Attachment[]>('GET', `/projects/${projectId}/tasks/${taskId}/attachments`),
  uploadTaskAttachment: (projectId: string, taskId: string, file: File) =>
    uploadFileTo(`/projects/${projectId}/tasks/${taskId}/attachments`, file),
  deleteAttachment: (attachmentId: string) =>
    request<void>('DELETE', `/attachments/${attachmentId}`),
  /**
   * The file's bytes, authenticated.
   *
   * A presigned URL would be nicer, but the object store is only reachable inside
   * the deployment's own network, so the browser has to come through the API.
   */
  fetchAttachmentBlob: async (attachmentId: string): Promise<Blob> => {
    const resp = await fetch(`${BASE}/attachments/${attachmentId}/content`, {
      headers: authHeaders(),
    })
    if (resp.status === 401) {
      sessionStorage.removeItem('pm_token')
      window.location.href = '/login'
    }
    if (!resp.ok) throw new Error(resp.statusText || 'Could not open the file')
    return resp.blob()
  },

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
  changeLabMemberRole: (labId: string, userId: string, role: string) =>
    request<LabMember_>('PUT', `/labs/${labId}/members/${userId}`, { role }),
  requestToJoinLab: (labId: string, lab_role: 'phd' | 'ms', message?: string) =>
    request<LabJoinRequest>('POST', `/labs/${labId}/join-requests`, { lab_role, message }),
  myLabJoinRequests: () => request<LabJoinRequest[]>('GET', '/labs/join-requests/mine'),
  pendingLabJoinRequests: () => request<LabJoinRequest[]>('GET', '/labs/join-requests/pending'),
  decideLabJoinRequest: (labId: string, id: string, decision: 'approve' | 'decline') =>
    request<LabJoinRequest>('POST', `/labs/${labId}/join-requests/${id}/${decision}`),

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
  verifyReferences: (pubId: string, text?: string) =>
    request<ReferenceCheck>('POST', `/publications/${pubId}/references/verify`, text ? { text } : {}),
  publicationFromRun: (runId: string) =>
    request<{ publication_id: string; version: number; verification: NumberCheck | null }>('POST', `/research-runs/${runId}/publication`),
  getVersion: (pubId: string, versionId: string) =>
    request<Version>('GET', `/publications/${pubId}/versions/${versionId}`),
  createVersion: (pubId: string, notes?: string) =>
    request<Version>('POST', `/publications/${pubId}/versions`, { notes }),
  // A human revision of one section (counts as human work in the AI disclosure).
  saveSectionText: (pubId: string, section: string, content: string) =>
    request<Version>('POST', `/publications/${pubId}/versions`, { section, content, notes: `Edited ${section}` }),
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
  draftFromExperiment: (projectId: string, experimentId: string, section: string, style: string = 'standard', publicationId?: string) =>
    request<{ publication_id: string; experiment_id: string; section: string; status: string }>(
      'POST', `/projects/${projectId}/experiments/${experimentId}/draft-to-publication?section=${section}&style=${style}${publicationId ? `&publication_id=${publicationId}` : ''}`
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

  // ── System Health ────────────────────────────────────────────────────────
  systemHealth: () => request<SystemHealth>('GET', '/system/health'),

  // ── Companion applications (CVAT, Curator, JupyterHub, …) ───────────────
  listIntegrations: () => request<IntegrationStatus[]>('GET', '/integrations'),

  // ── AutoResearchClaw runs ───────────────────────────────────────────────
  listResearchRuns: (projectId: string, expId: string) =>
    request<ResearchRun[]>('GET', `/projects/${projectId}/experiments/${expId}/research-runs`),
  startResearchRun: (projectId: string, expId: string, body: { topic?: string; mode?: ResearchMode; domain?: string; dataset_id?: string; irb_id?: string }) =>
    request<ResearchRun>('POST', `/projects/${projectId}/experiments/${expId}/research-runs`, body),
  researchGates: () => request<ResearchRun[]>('GET', '/research-runs/gates'),
  respondResearchGate: (runId: string, body: { action: GateAction; message?: string; guidance?: string; quality?: number }) =>
    request<ResearchRun>('POST', `/research-runs/${runId}/respond`, body),
  cancelResearchRun: (runId: string) => request<ResearchRun>('POST', `/research-runs/${runId}/cancel`),
  researchRunStages: (runId: string) => request<RunStages>('GET', `/research-runs/${runId}/stages`),
  researchUsage: () => request<ResearchUsage>('GET', '/research-runs/usage'),
  myTasks: () => request<{ id: string; title: string; status: string; priority: string; deadline: string | null; project_id: string; project_name: string }[]>('GET', '/me/tasks'),
  researchEvaluation: () => request<ResearchEvaluation>('GET', '/research-runs/evaluation'),
  researchDomains: () => request<ResearchDomain[]>('GET', '/research-runs/domains'),
  researchTopicCheck: (topic: string, domain?: string) =>
    request<TopicScore>('POST', '/research-runs/topic-check', { topic, domain }),
  researchDatasets: (projectId: string) => request<ResearchDataset[]>('GET', `/projects/${projectId}/research-datasets`),
  listResearchLessons: (labId: string) => request<ResearchLesson[]>('GET', `/labs/${labId}/research-lessons`),
  pinResearchLesson: (labId: string, lessonId: string, pinned: boolean) =>
    request<{ id: string; pinned: boolean }>('PATCH', `/labs/${labId}/research-lessons/${lessonId}`, { pinned }),
  deleteResearchLesson: (labId: string, lessonId: string) => request<void>('DELETE', `/labs/${labId}/research-lessons/${lessonId}`),
  researchRunFile: (runId: string, path: string) =>
    request<{ path: string; content: string }>('GET', `/research-runs/${runId}/file?path=${encodeURIComponent(path)}`),

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
export interface LabJoinRequest {
  id: string; lab_id: string; lab_name: string; user_id: string; username: string
  lab_role: 'phd' | 'ms'; message: string | null
  status: 'pending' | 'approved' | 'declined'; created_at: string; decided_at: string | null
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

export interface CvatProgress {
  tasks: number; jobs: number; jobs_done: number; frames_total: number; frames_done: number
  by_assignee: { name: string; jobs: number; jobs_done: number; frames: number; frames_done: number }[]
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
  /** manual | csv | cvat | ai_run */
  source?: string | null
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

/** One of the signed-in researcher's saved Curator selections — counts and status, never study keys. */
export interface CuratorSelection {
  id: string; name: string; created_at: string; expires_at: string
  studies: number; patients: number; instances: number; instances_unknown: number
  modalities: string[]; date_from: string | null; date_to: string | null
  modality: string | null; renders: boolean
  status: 'pending' | 'submitted' | string; submitted_at: string | null; medai_dataset_id: string | null
}

/** One project's access to a dataset (GET /datasets → grants[]). */
export interface DatasetGrant {
  id: string; project_id: string; project_name?: string | null
  admin_approved_at: string | null; granted_at: string; expires_at: string | null
  revoked_at: string | null; active: boolean; cvat_project_id?: number | null
}

/** A lab's dataset as the lab page lists it — the fields it shows, nothing else. */
export interface LabDataset {
  id: string; name: string; modality: string | null; status: string
  retention_until: string | null; grants: DatasetGrant[]
  estimated_bytes: number | null
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

/** A file in the project-wide view, with its owner. */
export interface ProjectAttachment {
  id: string
  filename: string
  content_type: string
  size_bytes: number
  classification: string
  created_at: string
  uploaded_by: string | null
  uploader_name: string | null
  owner_kind: 'task' | 'entry'
  owner_id: string
  owner_title: string
  experiment_id: string | null
}

export interface Attachment {
  id: string
  // Exactly one owner is set: an experiment entry or a task.
  entry_id: string | null
  task_id?: string | null
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
  verification?: NumberCheck | null
}
export interface NumberCheck {
  checked: number; verified: number; unverified: number; unverified_in_results: number
  recorded_values: number; examples: { value: string; context: string; strict: boolean }[]
}
export interface ReferenceCheck {
  references: { reference: string; status: 'verified' | 'suspicious' | 'hallucinated'; matched_title: string | null; url: string | null; source: string | null }[]
  counts: { verified: number; suspicious: number; hallucinated: number }
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
export interface IRB_ {
  id: string; title: string; institution: string; protocol_number: string; status: string
  approval_date: string | null; expiry_date: string | null
  project_id?: string; renewal_date?: string | null; documents?: string[]; notes?: string | null
  created_by?: string; created_at?: string; updated_at?: string
  approved_by?: string | null; approved_at?: string | null
}
export interface WikiPage_ { id: string; title: string; slug: string; content?: string; tags?: string[]; updated_at: string }
export interface SearchResults { projects: { id: string; name: string; type: string }[]; tasks: { id: string; title: string; project_id: string; type: string }[]; experiments: { id: string; name: string; project_id: string; type: string }[]; publications: { id: string; title: string; type: string }[] }

export interface Template {
  id: string; name: string; description: string; domain: string; icon: string
  phases: { name: string; color: string; position: number }[]
  experiment_types: { name: string; description: string }[]
  tasks: { title: string; description: string; phase: string; priority: string }[]
}

// ── AutoResearchClaw ─────────────────────────────────────────────────────────

export type ResearchMode = 'co-pilot' | 'gate-only' | 'full-auto' | 'step-by-step'
export type GateAction = 'approve' | 'reject' | 'edit' | 'skip' | 'rollback' | 'abort'
export interface ResearchRun {
  id: string; experiment_id: string; project_id: string; lab_id: string | null
  topic: string; mode: ResearchMode; dataset: string | null; irb_id: string | null
  status: 'queued' | 'running' | 'waiting' | 'done' | 'failed' | 'cancelled'
  stage: number | null; stage_name: string | null
  waiting: { stage: number; stage_name: string; reason: string; since: string; context_summary: string; output_files: string[] } | null
  error: string | null; created_at: string; updated_at: string
  domain?: string | null; queue_position?: number | null
  primary_metric?: number | null; primary_metric_std?: number | null; metric_direction?: string | null
  conditions?: string[]; pi_quality?: number | null; publication_id?: string | null
}
export interface RunStage {
  stage: number; status: string; duration_sec: number | null; decision: string | null
  error: string | null; artifacts: string[]; attempts: number; finished_at?: string | null
}
export interface TopicScore { novelty: number; specificity: number; feasibility: number; overall: number; suggestion: string }
export interface RunStages { stages: RunStage[]; topic_evaluation: TopicScore | null }
export interface ResearchUsage {
  requests_last_minute: number; limit_per_minute: number
  runs_running: number; runs_waiting: number; runs_queued: number; max_concurrent: number
}
export interface ResearchDomain { id: string; label: string; guidance: string }
export interface ResearchEvaluation {
  summary: { runs: number; finished: number; completion_rate: number | null; mean_interventions: number | null; mean_pi_quality: number | null }
  runs: { id: string; topic: string; status: string; mode: string; created_at: string; stage: number | null
    interventions: number; refines: number | null; pivots: number | null; retries: number | null
    unverified_in_paper: number | null; pi_quality: number | null; primary_metric: number | null }[]
  gates: { stage: number; stage_name: string | null; approved: number; redirected: number; total: number; approve_rate: number; advice: string }[]
  quality_trend: { id: string; created_at: string; status: string; pi_quality: number | null; interventions: number; refines: number | null; pivots: number | null; retries: number | null }[]
  gate_economics: {
    top_intervention_stages: { stage: number; stage_name: string | null; redirected: number; total: number; approve_rate: number }[]
    auto_approve_candidates: { stage: number; stage_name: string | null; approve_rate: number; total: number }[]
    min_decisions_for_advice: number
  }
  integrity: {
    papers_tracked: number
    papers_with_unverified_data: number
    unverified_total: number
    papers: { publication_id: string; title: string | null; pub_status: string | null; unverified_in_results: number | null; integrity_passed: boolean | null; integrity_at: string | null }[]
  }
  outcomes: {
    runs_with_publication: number
    runs_with_metric: number
    finished_with_paper: number
    mean_primary_metric: number | null
    papers: ResearchEvaluation['integrity']['papers']
  }
}
export interface ResearchDataset { id: string; name: string; modality: string | null; irb_ids: string[] }
export interface ResearchLesson {
  id: string; run_id: string | null; category: string; severity: number; pinned: boolean
  weight: number; created_at: string; lesson: { description?: string; stage_name?: string; severity?: string }
}

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

// ── Academic supervision ────────────────────────────────────────────────────

export interface StudentOverview {
  student_id: string; name: string; lab_name: string | null; level: string | null; thesis_title: string | null
  this_week: 'not_started' | 'draft' | 'submitted' | 'reviewed'; last_submitted: string | null
  weeks_submitted: number; weeks_window: number; risk: string | null; help_requested: string | null
  awaiting_review: number; followups_open: number; followups_overdue: number; tasks_open: number; tasks_overdue: number
  blocked: { title: string; blocker: string | null }[]; active_papers: number; attention: number; reasons: string[]
}

export interface SupervisorAssignment {
  id: string; student_id: string; student_name?: string | null; professor_name?: string | null; professor_id: string
  active_from: string; active_until: string | null; created_at: string
}

/** The workflow a project task actually has — the only values the API accepts. */
export type TaskStatus = 'todo' | 'in_progress' | 'done'

/** A project task as it appears in one week's update. */
export interface WeeklyTask {
  id: string; title: string; status: string; priority: string
  deadline: string | null; project_id: string; project_name: string
  item_id: string | null; item_status: string | null; item_progress_pct: number | null
  item_needs_help: boolean | null; report_id: string | null; report_status: string | null
}

export interface WeeklyTasks {
  week_start: string; report_id: string | null; report_status: string | null
  tasks: WeeklyTask[]
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
  id: string; student_id: string; student_name?: string | null; week_start: string
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
  professor_id?: string | null   // null: platform-wide (set by an admin)
  student_id?: string | null     // null: all of the professor's students at this level
  student_name?: string | null
}

export const supervisionApi = {
  myStudents: () => request<SupervisorAssignment[]>('GET', '/supervision/my-students'),
  studentsOverview: () => request<StudentOverview[]>('GET', '/supervision/students/overview'),
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
  /** One week's report, or null. Read-only: browsing must not create drafts. */
  weekReport: (week: string) =>
    request<WeeklyReport | null>('GET', `/supervision/weekly/report?week=${week}`),
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
  /** Assigned tasks for a week, and what the update already says about them. */
  weeklyTasks: (week?: string) =>
    request<WeeklyTasks>('GET', `/supervision/weekly/tasks${week ? `?week=${week}` : ''}`),
  /** Move a task and record it in the same week's update, in one action. */
  updateWeeklyTask: (
    taskId: string,
    data: { status?: TaskStatus; needs_help?: boolean; what_changed?: string; next_step?: string; blocker?: string },
    week?: string,
  ) => request<{ task: WeeklyTask; report_locked: boolean }>(
    'PUT', `/supervision/weekly/tasks/${taskId}${week ? `?week=${week}` : ''}`, data,
  ),
  startMeetingBrief: (studentId: string) =>
    request<{ job_id: string }>('POST', `/supervision/students/${studentId}/meeting-brief`),
  latestMeetingBrief: (studentId: string) =>
    request<MeetingBrief | null>('GET', `/supervision/students/${studentId}/meeting-brief`),
  startGroupAgenda: () => request<{ job_id: string }>('POST', '/supervision/meeting-agenda'),
  latestGroupAgenda: () => request<MeetingBrief | null>('GET', '/supervision/meeting-agenda'),
  getSkills: (studentId: string) => request<SkillsView>('GET', `/supervision/skills?student_id=${studentId}`),
  saveSkills: (studentId: string, scores: Record<string, number>, comment?: string) =>
    request<SkillAssessment>('PUT', '/supervision/skills', { student_id: studentId, scores, comment }),
  cohort: (term?: string) =>
    request<CohortView>('GET', `/supervision/cohort${term ? `?term=${encodeURIComponent(term)}` : ''}`),
  getAiJob: (id: string) => request<AiJob>('GET', `/ai-jobs/${id}`),
  listFollowups: (params: { studentId?: string; status?: 'open' | 'done' | 'dropped' } = {}) => {
    const q = new URLSearchParams()
    if (params.studentId) q.set('student_id', params.studentId)
    if (params.status) q.set('status', params.status)
    return request<Followup[]>('GET', `/supervision/followups${q.toString() ? `?${q}` : ''}`)
  },
  updateFollowup: (id: string, data: { status: 'open' | 'done' | 'dropped'; note?: string }) =>
    request<Followup>('PATCH', `/supervision/followups/${id}`, data),
  reviewReport: (id: string, data: {
    review_status: string; feedback?: string; risk_override?: string
    followups?: { text: string; due_date?: string }[]
  }) =>
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
      publication_gap?: PublicationGap
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
  renders?: boolean
  /** Storage reserved so far; null = none, and the bucket would have no size limit. */
  estimated_bytes?: number | null
}


/** A supervisor's request from a review; stays open across weeks until closed. */
export interface Followup {
  id: string; student_id: string; professor_id: string; report_id: string | null
  text: string; due_date: string | null; status: 'open' | 'done' | 'dropped'
  student_note: string | null; created_at: string; closed_at: string | null
  weeks_open: number; overdue: boolean
}


/** A stored AI meeting brief (one student) or group agenda. Markdown text. */
export interface MeetingBrief { id: string; student_id: string | null; content: string; created_at: string }


export interface SkillAssessment {
  student_id: string; perspective: 'self' | 'supervisor'; term: string
  scores: Record<string, number>; comment: string | null; updated_at: string
}
export interface SkillsView {
  skills: Record<string, string>; levels: Record<string, string>
  current_term: string; assessments: SkillAssessment[]
}


/** Distance to each publication requirement, the drafts that could close it, and an ETA
 *  only when there is a real pace (papers submitted since the journey began). */
export interface PublicationGap {
  pace_per_month: number | null; months_observed: number | null
  items: { requirement: string; target: number; current: number; gap: number; eta_months: number | null
           in_progress: { id: string; title: string; status: string }[] }[]
}


export interface CohortRow {
  student_id: string; name: string; weeks_elapsed: number; weeks_submitted: number
  submission_rate: number | null; high_risk_weeks: number
  followups_asked: number; followups_done: number; followups_open: number; followups_overdue: number
  median_days_to_close: number | null; papers_submitted: number
  skills_self: number | null; skills_supervisor: number | null
}
export interface CohortView { term: string; rows: CohortRow[]; medians: Record<string, number | null> }


// ── Paper Studio pipeline ───────────────────────────────────────────────────

export interface PaperContextSummary {
  publication_id: string
  summary: { counts: Record<string, number>; warnings: string[]; metric_count: number; experiment_ids: string[] }
  meta: { project_id: string | null; publication_id: string | null; project_name: string | null; publication_title: string | null; built_at: string }
  sources: Record<string, { id: string; label: string }[]>
  snapshots: { id: string; label: string | null; created_at: string; created_by: string | null }[]
}

export interface ClaimItem {
  id: string
  section: string
  claim_text: string
  evidence_ids: string[]
  sort_order: number
  status: string
}

export interface IntegrityCheck {
  id: string
  label: string
  passed: boolean
  detail: string
}

export interface PaperStages {
  publication_id: string
  status: string
  stages: Record<string, boolean>
  claim_count: number
  sections_done: string[]
  snapshot_count: number
  integrity: { passed: boolean; created_at: string; checks: IntegrityCheck[] } | null
}

export interface ReviewPoint {
  id: string
  publication_id: string
  round: number
  comment: string
  action: string | null
  section: string | null
  status: string
  created_at: string
}

export const paperApi = {
  context: (pubId: string) => request<PaperContextSummary>('GET', `/publications/${pubId}/context`),
  snapshot: (pubId: string, label?: string) =>
    request<{ snapshot: { id: string } | null; summary: PaperContextSummary['summary']; sources: PaperContextSummary['sources']; evidence_ids: string[] }>(
      'POST', `/publications/${pubId}/context`, { snapshot: true, label: label || 'Evidence pack' }
    ),
  outline: (pubId: string) => request<{ claims: ClaimItem[] }>('GET', `/publications/${pubId}/outline`),
  generateOutline: (pubId: string) =>
    request<{ claims: ClaimItem[] }>('POST', `/publications/${pubId}/outline/generate`),
  saveOutline: (pubId: string, claims: { section: string; claim_text: string; evidence_ids: string[] }[]) =>
    request<{ claims: ClaimItem[] }>('PUT', `/publications/${pubId}/outline`, { claims }),
  draftSection: (pubId: string, section: string, style = 'academic', extraInstructions?: string) =>
    request<{ section: string; evidence_ids: string[]; claim_count: number }>(
      'POST', `/publications/${pubId}/sections/draft`,
      { section, style, extra_instructions: extraInstructions || undefined }
    ),
  coherence: (pubId: string) => request<{ status: string }>('POST', `/publications/${pubId}/coherence`),
  integrity: (pubId: string) =>
    request<{ passed: boolean; checks: IntegrityCheck[]; blocking: string[] }>(
      'POST', `/publications/${pubId}/integrity`
    ),
  stages: (pubId: string) => request<PaperStages>('GET', `/publications/${pubId}/stages`),
  reviewPoints: (pubId: string) => request<{ points: ReviewPoint[] }>('GET', `/publications/${pubId}/review-points`),
  addReviewPoint: (pubId: string, data: { comment: string; action?: string; section?: string; round?: number }) =>
    request<ReviewPoint>('POST', `/publications/${pubId}/review-points`, data),
  updateReviewPoint: (pubId: string, pointId: string, data: { comment: string; action?: string; section?: string; status: string; round?: number }) =>
    request<ReviewPoint>('PUT', `/publications/${pubId}/review-points/${pointId}`, data),
  submitPack: (pubId: string) =>
    request<{ title: string; manuscript: { version_id: string | null; length: number; section: string | null }; claim_map_size: number; evidence_snapshot_id: string | null; ai_disclosure: { ai_versions: number; human_versions: number }; integrity_passed: boolean; open_review_points: number }>(
      'POST', `/publications/${pubId}/submit-pack`
    ),
}

// ---------------------------------------------------------------------------
// Cohort analysis (plan/cohort-analiz-roadmap.md)
// ---------------------------------------------------------------------------

export interface CohortColumnMeta {
  name: string
  dtype: string
  kind: 'numeric' | 'categorical' | 'datetime' | 'boolean'
  missing: number
  levels: number | null
}

export interface CohortParseReport {
  filename: string
  suffix: string
  encoding: string | null
  delimiter: string | null
  sheet: string | null
  lines: number | null
  rows: number
  columns: number
  skipped_lines: number
  blanks: number
  warnings: string[]
}

export interface CohortVersion {
  id: string
  table_id: string
  version_no: number
  rows: number
  columns: number
  columns_meta: CohortColumnMeta[]
  content_sha256: string
  parent_version_id: string | null
  parse_report: CohortParseReport | null
  note: string | null
  created_by: string
  created_at: string
}

export interface CohortPopulation {
  id: string
  table_id: string
  version_id: string
  name: string
  criteria: { id: string; family: string; kind: string; name: string; definition?: unknown }[]
  stages: { family: string; kind: string; n_in?: number; excluded?: number; n_out?: number }[]
  counts: {
    id: string
    name: string
    kind: string
    marginal_base: number
    marginal_in_stage: number
    sequential: number
  }[]
  n_base: number
  n_included: number
  fingerprint: string
  superseded_by: string | null
  created_by: string
  created_at: string
}

export interface CohortTable {
  id: string
  project_id: string
  lab_id: string | null
  name: string
  description: string | null
  data_origin: 'public' | 'synthetic' | 'governed'
  dataset_id: string | null
  config: { mask_families?: Record<string, unknown> }
  dictionary: Record<string, { label?: string; unit?: string }>
  created_by: string
  created_at: string
  updated_at: string
  versions: CohortVersion[]
  latest_version: CohortVersion | null
  populations: CohortPopulation[]
  active_population: CohortPopulation | null
}

export interface CohortCriterion {
  id: string
  family: string
  kind: 'inclusion' | 'exclusion'
  name: string
  description: string
  columns: string[]
}

export interface CohortAnalysisValue {
  name: string
  label: string | null
  value: number
  unit: string | null
  ci_low: number | null
  ci_high: number | null
  p_value: number | null
  n: number | null
}

export interface CohortCell {
  key: string
  label: string
}

export interface CohortRow {
  label: string
  column?: string
  kind?: 'numeric' | 'categorical'
  level?: string
  header?: boolean
  cells?: Record<string, string>
  value?: string
  missing?: number
  n?: number
  mean_sd?: string
  median_iqr?: string
  p?: number | null
  p_adjusted?: number | null
  effect?: { name: string; estimate: number; ci: number[] | null; magnitude: string } | null
  test?: string
  warnings?: string[]
}

export interface CohortRenderedTable {
  columns: (string | CohortCell)[]
  rows: CohortRow[]
  notes?: string[]
  adjustment?: string | null
  group?: string | null
  summary?: string
}

export interface CohortAnalysis {
  id: string
  population_id: string
  method: CohortMethod
  params: Record<string, unknown>
  result: Record<string, unknown>
  table: CohortRenderedTable | null
  n: number
  engine_version: string
  population_fingerprint: string
  status: 'current' | 'stale' | 'failed'
  stale_reason: string | null
  error: string | null
  created_by: string
  created_at: string
  values: CohortAnalysisValue[]
}

export interface CohortFlowBox {
  id: string
  label: string
  n: number
  kind: string
  details?: string[]
  added?: number
}

export interface CohortFlowExit {
  id: string
  after: string
  label: string
  n: number
  reasons: [string, number][]
  details?: string[]
}

export interface CohortFlow {
  main: CohortFlowBox[]
  exits: CohortFlowExit[]
  analyses: CohortFlowBox[]
  notes: string[]
  inconsistencies: string[]
}

export interface CohortQuality {
  version_id: string
  version_no: number
  rows: number
  columns: number
  score: number
  band: string
  dimensions: { key: string; label: string; score: number; weight: number; band: string }[]
  missing: { column: string; missing: number; share: number }[]
  duplicates: { rows: number; share: number }
  inconsistent: { column: string; issues: string[]; rows: number }[]
  non_uniform: { column: string; rows: number; variants: number; example: string }[]
  outliers: { column: string; rows: number; share: number; iqr_bounds: number[]; beyond_z: number }[]
  clinical_rules: { id: string; family: string; name: string; kind: string; rows: number }[]
  warnings: string[]
}

export interface CohortStep {
  id: string
  seq: number
  kind: 'import' | 'derive' | 'filter' | 'population'
  params: Record<string, unknown>
  data: Record<string, unknown>
  version_id: string
  out_version_id: string | null
  prev_hash: string
  hash: string
  created_by: string | null
  created_at: string
}

export interface CohortTrace {
  table_id: string
  steps: CohortStep[]
  chain: { verified: boolean; steps: number; problems: string[]; head: string | null }
}

export interface CohortReplay {
  table_id: string
  steps: { seq: number; kind: string; version_no: number | null; status: string; detail: string }[]
  reconciled: boolean
  problems: string[]
}

export type CohortMethod =
  | 'descriptive'
  | 'table1'
  | 'compare'
  | 'survival'
  | 'cox'
  | 'diagnostic'
  | 'ratio2x2'
  | 'logistic'
  | 'mantel_haenszel'
  | 'agreement'
  | 'mcar'
  | 'multiple_imputation'

export interface CohortAnalysisRequest {
  method: CohortMethod
  variables?: string[]
  group?: string | null
  outcome?: string | null
  kind?: string
  summary?: string
  adjust?: string
  alpha?: number
  /** Survival: follow-up time and event indicator (1 = event, 0 = censored). */
  time?: string | null
  event?: string | null
  /** Cox: the model's covariates. */
  covariates?: string[]
  /** Diagnostic accuracy: the test column and an optional fixed cut-off. */
  test?: string | null
  cutoff?: number | null
  pos_label?: string | null
  /** 2x2 association: the exposure column. */
  exposure?: string | null
  /** Logistic: the outcome level that counts as the event. */
  event_level?: string | null
  /** Mantel-Haenszel: the column whose strata are pooled. */
  stratum?: string | null
  /** Agreement: the measurement columns and which measure to compute. */
  raters?: string[]
  measure?: string
  weights?: string | null
  icc_model?: string
  /** Multiple imputation: what to pool, how many imputations, and the seed. */
  target?: 'compare' | 'logistic' | 'cox' | null
  m?: number
  maxit?: number
  seed?: number | null
}

/** Upload a cohort table file; the version endpoint takes multipart, not JSON. */
async function uploadCohortFile(path: string, file: File): Promise<CohortVersion> {
  const token = sessionStorage.getItem('pm_token')
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {}
  const form = new FormData()
  form.append('file', file)
  const resp = await fetch(`${BASE}${path}`, { method: 'POST', headers, body: form })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? resp.statusText)
  }
  return resp.json() as Promise<CohortVersion>
}

/** Download an endpoint that needs the bearer token (a plain link would not send it). */
async function downloadWithAuth(path: string, filename: string): Promise<void> {
  const token = sessionStorage.getItem('pm_token')
  const resp = await fetch(`${BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? resp.statusText)
  }
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export const cohortApi = {
  listTables: (projectId: string) =>
    request<CohortTable[]>('GET', `/projects/${projectId}/cohort/tables`),
  getTable: (projectId: string, tableId: string) =>
    request<CohortTable>('GET', `/projects/${projectId}/cohort/tables/${tableId}`),
  createTable: (
    projectId: string,
    data: { name: string; description?: string; data_origin: 'public' | 'synthetic' | 'governed'; dataset_id?: string },
  ) => request<CohortTable>('POST', `/projects/${projectId}/cohort/tables`, data),
  updateTable: (
    projectId: string,
    tableId: string,
    data: { name?: string; description?: string; config?: unknown; dictionary?: unknown },
  ) => request<CohortTable>('PATCH', `/projects/${projectId}/cohort/tables/${tableId}`, data),
  deleteTable: (projectId: string, tableId: string) =>
    request<void>('DELETE', `/projects/${projectId}/cohort/tables/${tableId}`),
  listCriteria: (projectId: string, tableId: string) =>
    request<CohortCriterion[]>('GET', `/projects/${projectId}/cohort/tables/${tableId}/criteria`),

  uploadVersion: (projectId: string, tableId: string, file: File) =>
    uploadCohortFile(`/projects/${projectId}/cohort/tables/${tableId}/versions`, file),
  preview: (projectId: string, tableId: string, versionId: string) =>
    request<{ version_id: string; rows: number; shown: number; columns: string[]; rows_data: Record<string, unknown>[] }>(
      'GET', `/projects/${projectId}/cohort/tables/${tableId}/versions/${versionId}/preview`,
    ),
  derive: (projectId: string, tableId: string, versionId: string, name: string, expression: string) =>
    request<CohortVersion>(
      'POST',
      `/projects/${projectId}/cohort/tables/${tableId}/versions/${versionId}/derive`,
      { name, expression },
    ),
  quality: (projectId: string, tableId: string, versionId: string) =>
    request<CohortQuality>('GET', `/projects/${projectId}/cohort/tables/${tableId}/versions/${versionId}/quality`),

  createPopulation: (projectId: string, tableId: string, name: string, criteria: string[]) =>
    request<CohortPopulation>('POST', `/projects/${projectId}/cohort/tables/${tableId}/populations`, { name, criteria }),
  flow: (projectId: string, tableId: string, populationId: string) =>
    request<CohortFlow>('GET', `/projects/${projectId}/cohort/tables/${tableId}/populations/${populationId}/flow`),

  runAnalysis: (projectId: string, tableId: string, populationId: string, body: CohortAnalysisRequest) =>
    request<CohortAnalysis>(
      'POST',
      `/projects/${projectId}/cohort/tables/${tableId}/populations/${populationId}/analyses`,
      body,
    ),
  listAnalyses: (projectId: string, tableId: string, populationId: string) =>
    request<CohortAnalysis[]>(
      'GET', `/projects/${projectId}/cohort/tables/${tableId}/populations/${populationId}/analyses`,
    ),
  getAnalysis: (projectId: string, tableId: string, analysisId: string) =>
    request<CohortAnalysis>('GET', `/projects/${projectId}/cohort/tables/${tableId}/analyses/${analysisId}`),
  publish: (projectId: string, tableId: string, analysisId: string, experimentId: string, names: string[]) =>
    request<{ analysis_id: string; experiment_id: string; published: { name: string; label: string | null; value: number }[] }>(
      'POST', `/projects/${projectId}/cohort/tables/${tableId}/analyses/${analysisId}/publish`,
      { experiment_id: experimentId, names },
    ),
  exportAnalysis: (projectId: string, tableId: string, analysisId: string, filename: string) =>
    downloadWithAuth(
      `/projects/${projectId}/cohort/tables/${tableId}/analyses/${analysisId}/export`, filename,
    ),

  /** The study dossier: provenance, participant flow, handling, missingness, results. */
  dossier: (projectId: string, tableId: string, analysisIds: string[], filename: string) => {
    const query = analysisIds.map(id => `analysis_id=${encodeURIComponent(id)}`).join('&')
    return downloadWithAuth(
      `/projects/${projectId}/cohort/tables/${tableId}/dossier${query ? `?${query}` : ''}`,
      filename,
    )
  },

  trace: (projectId: string, tableId: string) =>
    request<CohortTrace>('GET', `/projects/${projectId}/cohort/tables/${tableId}/trace`),
  replay: (projectId: string, tableId: string) =>
    request<CohortReplay>('POST', `/projects/${projectId}/cohort/tables/${tableId}/replay`),
}
