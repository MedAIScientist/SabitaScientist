import React, { useState } from 'react'
import { ProjectHeader } from '../components/ProjectHeader'
import { DatasetRequestDialog } from '../components/imaging/DatasetRequestDialog'
import { DatasetRequests } from '../components/imaging/DatasetRequests'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  api, CvatProjectSummary, DatasetSummary, PipelineRunSummary,
  ProjectAssetLink, SandboxSummary, WebKnossosDatasetSummary,
} from '../api'

type AssetKind = 'dataset' | 'pipeline_run' | 'cvat_project' | 'webknossos_dataset' | 'sandbox'

const STATUS_COLORS: Record<string, string> = {
  // datasets
  draft: '#6b7280', pi_approved: '#6366f1', approved: '#10b981',
  delivering: '#f59e0b', sealed: '#22c55e', expired: '#f43f5e', revoked: '#f43f5e',
  // runs
  pending: '#6b7280', running: '#f59e0b', completed: '#10b981', failed: '#f43f5e', verified: '#22c55e',
  // cvat / webknossos
  created: '#6b7280', importing: '#6366f1', annotating: '#f59e0b', reviewing: '#8b5cf6',
  exported: '#10b981', imported: '#6b7280', segmenting: '#f59e0b',
  proofreading: '#8b5cf6', archived: '#6b7280',
  // sandboxes
  provisioning: '#6b7280', active: '#10b981', expiring: '#f59e0b', terminated: '#f43f5e',
}

/**
 * Everything the project can work on, in one place: the imaging cohorts granted
 * to it, the de-identification runs that prepared them, the annotation and
 * segmentation work in progress, and the sandboxes. Each row also names the
 * experiments that reference it, which is the reverse of an experiment's DATA tab.
 */
export function ProjectDataPage() {
  const { id } = useParams<{ id: string }>()
  const projectId = id!
  const navigate = useNavigate()

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.getProject(projectId),
    enabled: Boolean(projectId),
  })
  const { data: datasets = [] } = useQuery({
    queryKey: ['datasets'], queryFn: () => api.listDatasets(),
  })
  const { data: runs = [] } = useQuery({
    queryKey: ['project-deid-runs', projectId],
    queryFn: () => api.listProjectDeidRuns(projectId),
    enabled: Boolean(projectId),
  })
  const { data: cvat = [] } = useQuery({
    queryKey: ['project-cvat', projectId],
    queryFn: () => api.listProjectCvat(projectId),
    enabled: Boolean(projectId),
  })
  const { data: wk = [] } = useQuery({
    queryKey: ['project-webknossos', projectId],
    queryFn: () => api.listProjectWebknossos(projectId),
    enabled: Boolean(projectId),
  })
  const { data: sandboxes = [] } = useQuery({
    queryKey: ['project-sandboxes', projectId],
    queryFn: () => api.listProjectSandboxes(projectId),
    enabled: Boolean(projectId),
  })
  const { data: apps = [] } = useQuery({ queryKey: ['integrations'], queryFn: api.listIntegrations })
  const [requesting, setRequesting] = useState(false)
  const { data: links = [] } = useQuery({
    queryKey: ['project-asset-links', projectId],
    queryFn: () => api.listProjectAssetLinks(projectId),
    enabled: Boolean(projectId),
  })

  // Reverse lineage, keyed the way the asset rows are.
  const usedBy = new Map<string, ProjectAssetLink[]>()
  for (const l of links) {
    const key = `${l.asset_type}:${l.asset_id}`
    usedBy.set(key, [...(usedBy.get(key) ?? []), l])
  }

  // Only cohorts actually released to this project: an unapproved or revoked
  // grant conveys nothing.
  const grantedDatasets = datasets.filter(d =>
    (d as DatasetSummary & { grants?: { project_id: string; admin_approved_at: string | null; revoked_at: string | null }[] })
      .grants?.some(g => g.project_id === projectId && g.admin_approved_at && !g.revoked_at),
  )

  const activeSandbox = sandboxes.find(sb => sb.status === 'active' || sb.status === 'expiring')

  const total = grantedDatasets.length + runs.length + cvat.length + wk.length + sandboxes.length
  const linked = links.length

  return (
    <div>
      <ProjectHeader projectId={projectId!} name={project?.name} actions={<>
        <AppLink app={apps.find(a => a.key === 'curator')} label="Open Curator (PACS)" />
        <AppLink app={apps.find(a => a.key === 'jupyter')} label="Open JupyterHub" subpath="hub/user-redirect/lab" />
        {activeSandbox?.access_url && (
          <a className="btn" href={activeSandbox.access_url} target="_blank" rel="noopener noreferrer"
            title={activeSandbox.expires_at ? `Workspace access ends ${activeSandbox.expires_at.slice(0, 10)}` : undefined}>
            Open workspace ↗
          </a>
        )}
        <button className="btn btn-primary" onClick={() => setRequesting(true)} disabled={!project}>+ Request imaging data</button>
      </>} />
      {requesting && project && <DatasetRequestDialog project={project} onClose={() => setRequesting(false)} />}
      <div className="page" style={{ maxWidth: 1000 }}>
        <p className="page-sub" style={{ marginTop: 0, marginBottom: 20 }}>
          {total} asset{total === 1 ? '' : 's'}
          {linked > 0 ? ` · ${linked} experiment link${linked === 1 ? '' : 's'}` : ''}
        </p>

        <DatasetRequests projectId={projectId} />

        {grantedDatasets.length > 0 && <JupyterAccess datasets={grantedDatasets} hubPath={apps.find(a => a.key === 'jupyter')?.path} />}

        <Section title="IMAGING DATASETS" hint="cohorts granted to this project">
          {grantedDatasets.map(d => (
            <Row
              key={d.id}
              name={d.name}
              status={d.status}
              detail={d.modality ?? undefined}
              usedBy={usedBy.get(`dataset:${d.id}`) ?? []}
              onOpenExperiment={expId => navigate(`/projects/${projectId}/experiments?exp=${expId}`)}
            />
          ))}
        </Section>

        <Section title="DE-IDENTIFICATION RUNS" hint="how the cohorts were prepared">
          {runs.map(r => (
            <Row
              key={r.id}
              name={`Run ${r.id.slice(0, 8)}`}
              status={r.status}
              detail={`${r.records_processed ?? 0} records · ${r.output_location}`}
              usedBy={usedBy.get(`pipeline_run:${r.id}`) ?? []}
              onOpenExperiment={expId => navigate(`/projects/${projectId}/experiments?exp=${expId}`)}
            />
          ))}
        </Section>

        <Section title="CVAT ANNOTATIONS" hint="image and video labelling">
          {cvat.map(c => (
            <Row
              key={c.id}
              name={c.name}
              status={c.status}
              detail={`${c.num_images} images · ${c.num_annotations} annotations`}
              externalHref="/cvat/"
              usedBy={usedBy.get(`cvat_project:${c.id}`) ?? []}
              onOpenExperiment={expId => navigate(`/projects/${projectId}/experiments?exp=${expId}`)}
            />
          ))}
        </Section>

        <Section title="WEBKNOSSOS SEGMENTATIONS" hint="3D EM volume annotation">
          {wk.map(w => (
            <Row
              key={w.id}
              name={w.name}
              status={w.status}
              detail={`${w.num_volumes} volumes · ${w.num_skeletons} skeletons`}
              usedBy={usedBy.get(`webknossos_dataset:${w.id}`) ?? []}
              onOpenExperiment={expId => navigate(`/projects/${projectId}/experiments?exp=${expId}`)}
            />
          ))}
        </Section>

        <Section title="SANDBOXES" hint="isolated analysis environments">
          {sandboxes.map(s => (
            <Row
              key={s.id}
              name={s.name}
              status={s.status}
              detail={s.expires_at ? `expires ${s.expires_at.slice(0, 10)}` : undefined}
              externalHref={s.access_url ?? undefined}
              usedBy={usedBy.get(`sandbox:${s.id}`) ?? []}
              onOpenExperiment={expId => navigate(`/projects/${projectId}/experiments?exp=${expId}`)}
            />
          ))}
        </Section>

        {total === 0 && (
          <div style={{
            padding: 32, textAlign: 'center', color: 'var(--text-dim)',
            fontFamily: 'var(--font-mono)', fontSize: 15, lineHeight: 1.6,
          }}>
            No data assets for this project yet.<br />
            Cohorts are released from a lab's dataset governance, and processing,
            annotation and sandbox work is created per project.
          </div>
        )}
      </div>
    </div>
  )
}

function Section({ title, hint, children }: {
  title: string; hint: string; children: React.ReactNode
}) {
  const items = React.Children.toArray(children)
  return (
    <div style={{ marginBottom: 22 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 8 }}>
        <div style={{
          fontSize: 14, fontWeight: 700, letterSpacing: '0.04em',
          fontFamily: 'var(--font-mono)', color: 'var(--text-heading)',
        }}>{title}</div>
        <div style={{ fontSize: 13, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
          {items.length} · {hint}
        </div>
      </div>
      {items.length === 0 ? (
        <div style={{
          fontSize: 15, color: 'var(--text-3)', fontFamily: 'var(--font-mono)',
          padding: '6px 0',
        }}>— none —</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>{children}</div>
      )}
    </div>
  )
}

function Row({ name, status, detail, usedBy, externalHref, onOpenExperiment }: {
  name: string
  status: string
  detail?: string
  usedBy: ProjectAssetLink[]
  externalHref?: string
  onOpenExperiment: (experimentId: string) => void
}) {
  const color = STATUS_COLORS[status] ?? '#6b7280'
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      background: 'var(--surface-card)', border: '1px solid var(--border)',
      borderLeft: `3px solid ${color}`, borderRadius: '0 8px 8px 0',
      padding: '12px 16px',
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 16, color: 'var(--text-heading)' }}>{name}</div>
        <div style={{
          fontSize: 13, color: 'var(--text-dim)',
          fontFamily: 'var(--font-mono)', marginTop: 2,
        }}>
          {status.toUpperCase()}{detail ? ` · ${detail}` : ''}
        </div>
        {usedBy.length > 0 && (
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6,
          }}>
            <span style={{
              fontSize: 12, color: 'var(--text-3)', fontFamily: 'var(--font-mono)',
            }}>Used by</span>
            {usedBy.map((l, i) => (
              <button
                key={`${l.experiment_id}-${l.role}-${i}`}
                onClick={() => onOpenExperiment(l.experiment_id)}
                title={`${l.role} in this experiment`}
                style={{
                  cursor: 'pointer', padding: '1px 7px', borderRadius: 3,
                  background: 'rgba(var(--accent-rgb),0.08)',
                  border: '1px solid rgba(var(--accent-rgb),0.22)',
                  color: 'var(--accent)', fontSize: 12, fontFamily: 'var(--font-mono)',
                }}
              >⚗ {l.experiment_name}</button>
            ))}
          </div>
        )}
      </div>
      <span style={{
        fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)',
        color, background: `${color}14`, border: `1px solid ${color}30`,
        borderRadius: 4, padding: '2px 8px', whiteSpace: 'nowrap',
      }}>{status.replace('_', ' ').toUpperCase()}</span>
      {externalHref && (
        <a href={externalHref} target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'none' }}>
          <button style={{
            cursor: 'pointer', padding: '5px 10px', borderRadius: 5,
            background: 'transparent', border: '1px solid var(--border)',
            color: 'var(--text-muted)', fontSize: 13,
            fontFamily: 'var(--font-mono)', fontWeight: 700,
          }}>Open ↗</button>
        </a>
      )}
    </div>
  )
}


/** A companion app link; shown disabled (with the reason) when the probe says it is down. */
function AppLink({ app, label, subpath = '' }: {
  app?: { path: string; up: boolean; http_status: number | null }; label: string
  /** Deep link inside the app, e.g. JupyterHub's user-redirect to the caller's own server. */
  subpath?: string
}) {
  if (!app) return null
  if (!app.up) {
    return <span className="btn" aria-disabled="true" style={{ opacity: 0.55, cursor: 'not-allowed' }}
      title={`Not reachable right now${app.http_status ? ` (HTTP ${app.http_status})` : ''}`}>{label} · offline</span>
  }
  return <a className="btn" href={app.path + subpath} target="_blank" rel="noopener noreferrer">{label} ↗</a>
}


/** Where a granted cohort is in delivery, in the words a researcher needs. */
const DELIVERY: Record<string, string> = {
  approved: 'approved, waiting for delivery from PACS',
  delivering: 'being delivered — files are still arriving',
  sealed: 'delivered and sealed',
}

/**
 * How to reach the granted cohorts from a notebook. Access follows project
 * membership: platform-control grants each researcher's NEXT JupyterHub session
 * key read access to the buckets of every dataset granted to their projects.
 */
function JupyterAccess({ datasets, hubPath }: { datasets: DatasetSummary[]; hubPath?: string }) {
  const [copied, setCopied] = useState<string | null>(null)
  const copy = (text: string) => {
    navigator.clipboard?.writeText(text).then(() => { setCopied(text); setTimeout(() => setCopied(null), 1500) })
  }
  return (
    <details className="request" style={{ marginBottom: 24 }} open>
      <summary style={{ cursor: 'pointer', fontWeight: 600, color: 'var(--text-heading)' }}>Using this data in JupyterHub</summary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10, fontSize: 13.5, color: 'var(--text-2)' }}>
        <p>
          As a member of this project, your JupyterHub session can read the buckets below. Access is added to your
          <b> next</b> session: if a dataset was granted after you started your server, restart it
          {hubPath ? <> (<a href={`${hubPath}hub/home`} target="_blank" rel="noopener noreferrer">Hub control panel</a> → Stop My Server → Start)</> : ''}.
        </p>
        <table className="bucket-table">
          <thead><tr><th>Dataset</th><th>Bucket</th><th>Status</th><th /></tr></thead>
          <tbody>
            {datasets.map(d => (
              <tr key={d.id}>
                <td>{d.name}</td>
                <td><code>{d.bucket || '—'}</code></td>
                <td>{DELIVERY[d.status] ?? d.status}</td>
                <td>{d.bucket && <button className="btn" style={{ height: 26 }} onClick={() => copy(d.bucket!)}>{copied === d.bucket ? 'Copied' : 'Copy'}</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
