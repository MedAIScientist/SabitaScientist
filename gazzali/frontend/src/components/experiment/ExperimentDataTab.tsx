import React, { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ExperimentAsset, ExperimentAssetRole, ExperimentAssetType } from '../../api'

/** The role follows from the kind of thing linked, so nobody has to pick it. */
const ROLE_FOR: Record<ExperimentAssetType, ExperimentAssetRole> = {
  dataset: 'input', pipeline_run: 'processing', cvat_project: 'output', webknossos_dataset: 'output', sandbox: 'reference',
}
const KIND_TEXT: Record<ExperimentAssetType, string> = {
  dataset: 'Imaging cohort', pipeline_run: 'De-identification', cvat_project: 'CVAT annotation',
  webknossos_dataset: 'WebKnossos segmentation', sandbox: 'Analysis sandbox',
}
const USABLE_DATASET = ['approved', 'delivering', 'sealed']

interface Option { type: ExperimentAssetType; id: string; label: string; detail: string; cvatId?: number }

const muted: React.CSSProperties = { fontSize: 13, color: 'var(--text-3)', margin: 0 }

function Step({ n, title, hint, done, children }: { n: number; title: string; hint: string; done: boolean; children: React.ReactNode }) {
  return (
    <section className="card" style={{ padding: 12, marginBottom: 10 }} aria-label={title}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
        <span aria-hidden style={{ width: 22, height: 22, borderRadius: '50%', display: 'grid', placeItems: 'center', fontSize: 12, fontWeight: 700, flex: 'none',
          background: done ? '#10b981' : 'transparent', color: done ? '#fff' : 'var(--text-3)', border: done ? 'none' : '1px solid var(--border)' }}>{done ? '✓' : n}</span>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15 }}>{title}</div>
          <div style={muted}>{hint}</div>
        </div>
      </div>
      {children}
    </section>
  )
}

function LinkedRow({ a, onUnlink, extra }: { a: ExperimentAsset; onUnlink: () => void; extra?: React.ReactNode }) {
  return (
    <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 6, padding: '7px 9px', marginBottom: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 15 }}>{a.label ?? a.asset_id.slice(0, 8)}</div>
          <div style={muted}>{KIND_TEXT[a.asset_type]}{a.detail ? ` · ${a.detail}` : ''}</div>
        </div>
        <button className="btn" onClick={onUnlink} aria-label={`Remove ${a.label ?? 'link'}`} title="Remove from this experiment">✕</button>
      </div>
      {extra}
    </div>
  )
}

function Suggestions({ options, onUse, busy, empty }: { options: Option[]; onUse: (o: Option) => void; busy: boolean; empty: string }) {
  if (options.length === 0) return <p style={muted}>{empty}</p>
  return (
    <div style={{ display: 'grid', gap: 4 }}>
      <div style={{ ...muted, fontWeight: 600 }}>Available in this project</div>
      {options.map(o => (
        <div key={`${o.type}:${o.id}`} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
          <span style={{ flex: 1, minWidth: 0 }}>{o.label} <span style={{ color: 'var(--text-3)', fontSize: 12 }}>· {KIND_TEXT[o.type]} · {o.detail}</span></span>
          <button className="btn" disabled={busy} onClick={() => onUse(o)}>Use</button>
        </div>
      ))}
    </div>
  )
}

/** Live CVAT progress: finished frames out of all frames, per annotator. */
function CvatProgressBar({ projectId, assetId }: { projectId: string; assetId: string }) {
  const { data, error, isLoading } = useQuery({ queryKey: ['cvat-progress', projectId, assetId], queryFn: () => api.cvatProgress(projectId, assetId), retry: false })
  if (isLoading) return <p style={{ ...muted, marginTop: 6 }}>Checking CVAT…</p>
  if (error) return <p style={{ ...muted, marginTop: 6, color: '#f59e0b' }}>Progress unavailable: {(error as Error).message}</p>
  if (!data || data.frames_total === 0) return <p style={{ ...muted, marginTop: 6 }}>No images in CVAT yet. Add a task with images in CVAT to start annotating.</p>
  const pct = Math.round((data.frames_done / data.frames_total) * 100)
  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
        <span>{data.frames_done} of {data.frames_total} images finished</span><span>{pct}%</span>
      </div>
      <div role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} style={{ height: 6, background: 'var(--border)', borderRadius: 3 }}>
        <div style={{ width: `${pct}%`, height: 6, background: '#10b981', borderRadius: 3 }} />
      </div>
      {data.by_assignee.length > 1 && (
        <div style={{ ...muted, marginTop: 4 }}>{data.by_assignee.map(p => `${p.name}: ${p.frames_done}/${p.frames}`).join(' · ')}</div>
      )}
    </div>
  )
}

/**
 * The experiment's data as a flow: which cohort went in (and how it was de-identified),
 * where it is annotated, and how the annotation becomes measured numbers in Results.
 * Links point at assets the project owns; nothing is copied.
 */
export function ExperimentDataTab({ projectId, experimentId, onOpenResults }: {
  projectId: string; experimentId: string; onOpenResults?: () => void
}) {
  const qc = useQueryClient()
  const [msg, setMsg] = useState<{ text: string; error?: boolean } | null>(null)
  const [adding, setAdding] = useState(false)
  const { data: assets = [], isLoading } = useQuery({
    queryKey: ['experiment-assets', projectId, experimentId], queryFn: () => api.listExperimentAssets(projectId, experimentId),
  })
  const { data: options = [] } = useQuery({
    queryKey: ['asset-options', projectId],
    queryFn: async (): Promise<Option[]> => {
      const [datasets, runs, cvat, wk] = await Promise.all([
        api.listDatasets(), api.listProjectDeidRuns(projectId), api.listProjectCvat(projectId), api.listProjectWebknossos(projectId),
      ])
      return [
        ...datasets.filter(d => USABLE_DATASET.includes(d.status)).map(d => ({ type: 'dataset' as const, id: d.id, label: d.name, detail: d.status })),
        ...runs.map(r => ({ type: 'pipeline_run' as const, id: r.id, label: `Run ${r.id.slice(0, 8)}`, detail: `${r.status} · ${r.records_processed ?? 0} records` })),
        ...cvat.map(c => ({ type: 'cvat_project' as const, id: c.id, label: c.name, detail: c.status, cvatId: c.cvat_id })),
        ...wk.map(w => ({ type: 'webknossos_dataset' as const, id: w.id, label: w.name, detail: w.status })),
      ]
    },
  })
  const { data: metrics = [] } = useQuery({
    queryKey: ['experiment-metrics', projectId, experimentId], queryFn: () => api.listExperimentMetrics(projectId, experimentId),
  })

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['experiment-assets', projectId, experimentId] })
    qc.invalidateQueries({ queryKey: ['experiments', projectId] })
  }
  const fail = (e: unknown) => setMsg({ text: e instanceof Error ? e.message : 'Something went wrong', error: true })
  const link = useMutation({
    mutationFn: (o: Option) => api.linkExperimentAsset(projectId, experimentId, { asset_type: o.type, asset_id: o.id, role: ROLE_FOR[o.type] }),
    onSuccess: () => { refresh(); setMsg(null) }, onError: fail,
  })
  const unlink = useMutation({
    mutationFn: (a: ExperimentAsset) => api.unlinkExperimentAsset(projectId, experimentId, a.asset_type, a.asset_id),
    onSuccess: refresh, onError: fail,
  })
  const toResults = useMutation({
    mutationFn: (a: ExperimentAsset) => api.importCvatMetrics(projectId, experimentId, a.asset_id),
    onSuccess: r => {
      qc.invalidateQueries({ queryKey: ['experiment-metrics', projectId, experimentId] })
      setMsg({ text: `${r.saved} numbers sent to Results: ${r.summary.frames_annotated} images annotated, ${Object.entries(r.summary.labels).map(([k, v]) => `${v} ${k}`).join(', ')}.` })
    },
    onError: fail,
  })

  const linked = (types: ExperimentAssetType[]) => assets.filter(a => types.includes(a.asset_type))
  const unlinkedOptions = (types: ExperimentAssetType[]) =>
    options.filter(o => types.includes(o.type) && !assets.some(a => a.asset_type === o.type && a.asset_id === o.id))
  const cvatIdOf = (assetId: string) => options.find(o => o.type === 'cvat_project' && o.id === assetId)?.cvatId
  const dataLinks = linked(['dataset', 'pipeline_run'])
  const annLinks = linked(['cvat_project', 'webknossos_dataset'])
  const cvatLinks = annLinks.filter(a => a.asset_type === 'cvat_project')
  const busy = link.isPending || unlink.isPending

  if (isLoading) return <p style={muted}>Loading…</p>

  // Optional: most experiments use no imaging cohort or annotation, so ask nothing of them.
  if (assets.length === 0 && !adding) {
    return (
      <section className="card" style={{ padding: 14 }}>
        <div style={{ fontWeight: 700, fontSize: 15 }}>No data linked</div>
        <p style={{ ...muted, margin: '4px 0 10px', fontSize: 14 }}>
          Optional. Use this only if the experiment works on an imaging cohort or an annotation project;
          then progress and annotation counts can flow into Results.
        </p>
        <button className="btn" onClick={() => setAdding(true)}>Link a cohort or annotation</button>
      </section>
    )
  }

  return (
    <div>
      {msg && <div role={msg.error ? 'alert' : 'status'} className={msg.error ? 'msg msg-error' : 'msg'} style={{ marginBottom: 10 }}>{msg.text}</div>}

      <Step n={1} title="Data" hint="Optional: the cohort this experiment uses, and how it was de-identified." done={dataLinks.length > 0}>
        {dataLinks.map(a => <LinkedRow key={`${a.asset_type}:${a.asset_id}`} a={a} onUnlink={() => unlink.mutate(a)} />)}
        <Suggestions options={unlinkedOptions(['dataset', 'pipeline_run'])} onUse={o => link.mutate(o)} busy={busy}
          empty={dataLinks.length ? '' : 'No approved cohort in this project. Skip this if the experiment does not use one.'} />
      </Step>

      <Step n={2} title="Annotation" hint="Optional: where the images are labelled. Progress comes live from CVAT." done={annLinks.length > 0}>
        {annLinks.map(a => (
          <LinkedRow key={`${a.asset_type}:${a.asset_id}`} a={a} onUnlink={() => unlink.mutate(a)} extra={a.asset_type === 'cvat_project' && (
            <>
              <CvatProgressBar projectId={projectId} assetId={a.asset_id} />
              {cvatIdOf(a.asset_id) != null && <a className="text-link" href={`/cvat/projects/${cvatIdOf(a.asset_id)}`} target="_blank" rel="noreferrer" style={{ fontSize: 13 }}>Open in CVAT ↗</a>}
            </>
          )} />
        ))}
        <Suggestions options={unlinkedOptions(['cvat_project', 'webknossos_dataset'])} onUse={o => link.mutate(o)} busy={busy}
          empty={annLinks.length ? '' : 'No annotation project in this project. Skip this if nothing is annotated.'} />
      </Step>

      {cvatLinks.length > 0 && <Step n={3} title="Results" hint="Send annotation counts to Results as measured numbers that paper drafts can use." done={metrics.length > 0}>
        {cvatLinks.map(a => (
          <div key={a.asset_id} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span style={{ flex: 1, fontSize: 14 }}>{a.label}</span>
            <button className="btn btn-primary" disabled={toResults.isPending} onClick={() => toResults.mutate(a)}>
              {toResults.isPending ? 'Counting…' : 'Send counts to Results'}
            </button>
          </div>
        ))}
        <p style={{ ...muted, marginTop: 4 }}>
          {metrics.length} measured number{metrics.length === 1 ? '' : 's'} in Results.{' '}
          {onOpenResults && <button className="text-link" style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer' }} onClick={onOpenResults}>Open Results →</button>}
        </p>
      </Step>}

      {linked(['sandbox']).length > 0 && (
        <section className="card" style={{ padding: 12 }} aria-label="Other links">
          <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 6 }}>Other links</div>
          {linked(['sandbox']).map(a => <LinkedRow key={a.asset_id} a={a} onUnlink={() => unlink.mutate(a)} />)}
        </section>
      )}
    </div>
  )
}
