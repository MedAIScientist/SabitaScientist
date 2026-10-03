import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ImagingInboxItem } from '../../api'

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
  const text = ACTION_TEXT[item.action]
  const act = useMutation({
    mutationFn: () => {
      switch (item.action) {
        case 'pi-approve': return api.piApproveDataset(item.dataset_id)
        case 'admin-approve': return api.adminApproveDataset(item.dataset_id, retention)
        case 'propose-grant': return api.proposeDatasetGrant(item.dataset_id, item.project_id!)
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
        {item.action === 'admin-approve' && (
          <label className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <span>Keep data until</span>
            <input className="input" type="date" value={retention} onChange={e => setRetention(e.target.value)} style={{ width: 170 }} />
          </label>
        )}
        <button className="btn btn-primary" disabled={blocked || act.isPending || (item.action === 'admin-approve' && !retention)}
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
