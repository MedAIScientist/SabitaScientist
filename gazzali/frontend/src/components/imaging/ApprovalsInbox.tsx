import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ImagingInboxItem } from '../../api'
import { DatasetId } from './DatasetId'
import { GIB, gibToBytes } from './storage'

const ACTION_TEXT: Record<ImagingInboxItem['action'], { title: string; button: string }> = {
  'pi-approve': { title: 'Approve as lab PI', button: 'Approve' },
  'admin-approve': { title: 'Final approval (platform admin)', button: 'Approve & release' },
  'propose-grant': { title: 'Share with the requesting project', button: 'Share with project' },
  'approve-grant': { title: 'Activate project access (platform admin)', button: 'Activate access' },
}

function defaultRetention(): string {
  const d = new Date()
  d.setFullYear(d.getFullYear() + 2)
  return d.toISOString().slice(0, 10)
}

function Item({ item }: { item: ImagingInboxItem }) {
  const qc = useQueryClient()
  const [retention, setRetention] = useState(item.retention_until ?? defaultRetention())
  // The storage to reserve, in GiB — it becomes the delivered bucket's size limit.
  const [storage, setStorage] = useState(item.estimated_bytes ? String(Math.ceil((item.estimated_bytes / GIB) * 10) / 10) : '')
  const storageBytes = gibToBytes(storage)
  // Where the project will use the data. JupyterHub read access comes with every
  // share; CVAT additionally stages the viewable images as annotation tasks. The default
  // follows what the requester asked for: viewable images were requested FOR annotation, so a
  // request with them starts on "JupyterHub and CVAT" (2026-10-17: a student who asked for
  // viewable images was shown to their PI as wanting JupyterHub only).
  const canAnnotate = item.renders !== false
  const [annotate, setAnnotate] = useState(canAnnotate)
  const [taskSize, setTaskSize] = useState('')
  const text = ACTION_TEXT[item.action]
  const act = useMutation({
    mutationFn: () => {
      switch (item.action) {
        case 'pi-approve': return api.piApproveDataset(item.dataset_id)
        case 'admin-approve': return api.adminApproveDataset(item.dataset_id, retention, storageBytes ?? undefined)
        case 'propose-grant': return api.proposeDatasetGrant(item.dataset_id, item.project_id!,
          annotate ? { annotate: true, ...(taskSize ? { task_size: Number(taskSize) } : {}) } : {})
        case 'approve-grant': return api.approveDatasetGrant(item.dataset_id, item.grant_id!)
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['imaging-inbox'] })
      qc.invalidateQueries({ queryKey: ['dataset-requests'] })
      qc.invalidateQueries({ queryKey: ['datasets'] })
    },
  })
  const blocked = item.blockers.length > 0

  return (
    <div className="inbox-item">
      <div className="inbox-kind">{text.title}</div>
      <div className="request-title">{item.dataset_name}{item.modality && <span className="chip">{item.modality}</span>}</div>
      <p className="inbox-purpose">{item.purpose}</p>
      <DatasetId id={item.dataset_id} />
      <dl className="inbox-facts">
        <div><dt>Studies</dt><dd>{item.accession_count}</dd></div>
        {item.lab_name && <div><dt>Lab</dt><dd>{item.lab_name}</dd></div>}
        {item.project_name && <div><dt>Project</dt><dd>{item.project_name}</dd></div>}
        {item.requested_by && <div><dt>Requested by</dt><dd>{item.requested_by}</dd></div>}
        <div><dt>IRB</dt><dd>{item.irbs.length ? item.irbs.map(i => `${i.title} (${i.status}${i.expiry_date ? `, until ${i.expiry_date}` : ''})`).join('; ') : '—'}</dd></div>
      </dl>
      {blocked && (
        <ul className="blockers" role="alert">{item.blockers.map(b => <li key={b}>{b}</li>)}</ul>
      )}
      <div className="inbox-actions">
        {item.action === 'propose-grant' && (
          <fieldset className="field" style={{ border: 'none', padding: 0, margin: 0 }}>
            <p className="hint">
              {item.requested_by ?? 'The requester'} asked for {canAnnotate
                ? 'viewable images too — for annotation in CVAT'
                : 'the DICOM files only — for JupyterHub'}.
            </p>
            <span>Use in</span>
            <label className="check">
              <input type="radio" name={`use-${item.dataset_id}`} checked={!annotate} onChange={() => setAnnotate(false)} />
              <span>JupyterHub <small>(read the DICOM files)</small></span>
            </label>
            <label className="check">
              <input type="radio" name={`use-${item.dataset_id}`} checked={annotate} disabled={!canAnnotate}
                onChange={() => setAnnotate(true)} />
              <span>JupyterHub and CVAT <small>(also stage the viewable images as annotation tasks)</small></span>
            </label>
            {!canAnnotate && <p className="hint">This dataset was approved without viewable images, so it cannot be annotated in CVAT.</p>}
            {annotate && (
              <label className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <span>Images per task</span>
                <input className="input" type="number" min={1} max={500} value={taskSize} placeholder="one task per study"
                  onChange={e => setTaskSize(e.target.value)} style={{ width: 170 }} />
              </label>
            )}
          </fieldset>
        )}
        {item.action === 'admin-approve' && (
          <label className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <span>Keep data until</span>
            <input className="input" type="date" value={retention} onChange={e => setRetention(e.target.value)} style={{ width: 170 }} />
          </label>
        )}
        {item.action === 'admin-approve' && (
          <label className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span>Storage to reserve (GiB)</span>
            <input className="input" inputMode="decimal" aria-label="Storage to reserve (GiB)" value={storage}
              onChange={e => setStorage(e.target.value)} placeholder="e.g. 5" style={{ width: 110 }} />
            <span className="hint" style={{ flexBasis: '100%' }}>
              {storageBytes
                ? 'Becomes the bucket\u2019s size limit. Use the estimate Curator shows for this cohort, with some margin.'
                : 'Without it the bucket has no size limit: a larger cohort than expected fills shared storage instead of stopping at its own.'}
            </span>
          </label>
        )}
        <button className="btn btn-primary" disabled={blocked || act.isPending || (item.action === 'admin-approve' && (!retention || (storage.trim() !== '' && storageBytes === null)))}
          onClick={() => act.mutate()}>{act.isPending ? 'Working…' : text.button}</button>
      </div>
      {act.isError && <div className="msg msg-error" role="alert">{(act.error as Error).message}</div>}
    </div>
  )
}

/**
 * Imaging-data steps waiting on the signed-in PI or admin. Renders nothing when
 * there is nothing to do, so it can sit on any dashboard.
 */
export function ApprovalsInbox() {
  const { data: items = [] } = useQuery({ queryKey: ['imaging-inbox'], queryFn: api.imagingInbox, refetchInterval: 60_000 })
  if (items.length === 0) return null
  return (
    <section aria-label="Needs your approval" style={{ margin: '0 0 26px' }}>
      <h3 className="section-title">Needs your approval <span className="count">{items.length}</span></h3>
      <div className="inbox-grid">
        {items.map(i => <Item key={`${i.action}-${i.dataset_id}-${i.grant_id ?? ''}`} item={i} />)}
      </div>
    </section>
  )
}
