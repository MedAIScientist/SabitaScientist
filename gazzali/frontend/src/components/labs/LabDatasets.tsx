import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, DatasetGrant, LabDataset } from '../../api'
import { DatasetId } from '../imaging/DatasetId'
import { formatGib, gibToBytes } from '../imaging/storage'

/** The words for what revoking does — stated before the click, because it is not instant. */
export function revokeConsequence(grant: DatasetGrant): string {
  if (!grant.admin_approved_at) {
    return 'This share was never approved, so nobody reads the dataset through it. Withdrawing it stops the approval.'
  }
  const base = 'Its members lose read access within seconds — notebooks already running included. '
    + 'Copies already made are not recalled.'
  // An annotation share staged the viewable images INTO the project — its own bucket and its CVAT
  // tasks. Revoking stops further staging; it does not delete what was staged, which the project
  // can read with no end date. Saying so is the difference between revoking and believing it.
  return grant.cvat_project_id
    ? `${base} This share also copied the viewable images into the project's own storage and its CVAT tasks; `
      + 'revoking does not remove those copies — delete them there if they must go.'
    : base
}

function GrantRow({ ds, grant }: { ds: LabDataset; grant: DatasetGrant }) {
  const qc = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const project = grant.project_name || grant.project_id
  const revoke = useMutation({
    mutationFn: () => api.revokeDatasetGrant(ds.id, grant.id),
    onSuccess: () => {
      setConfirming(false)
      qc.invalidateQueries({ queryKey: ['lab-datasets'] })
      qc.invalidateQueries({ queryKey: ['imaging-inbox'] })
    },
  })
  const approved = !!grant.admin_approved_at
  return (
    <li style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '8px 0', borderTop: '1px solid var(--border-subtle)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <b>{project}</b>
        <span className="hint">
          {approved ? `shared since ${grant.admin_approved_at!.slice(0, 10)}` : 'awaiting admin approval'}
          {grant.cvat_project_id ? ' · with CVAT annotation' : ''}
          {grant.expires_at ? ` · until ${grant.expires_at.slice(0, 10)}` : ''}
        </span>
        {!confirming && (
          <button type="button" className="btn" style={{ marginLeft: 'auto' }} onClick={() => setConfirming(true)}
            aria-label={`${approved ? 'Revoke' : 'Withdraw'} ${project}'s access to ${ds.name}`}>
            {approved ? 'Revoke access' : 'Withdraw'}
          </button>
        )}
      </div>
      {confirming && (
        <div role="group" aria-label={`Confirm revoking ${project}`} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span className="hint">{revokeConsequence(grant)}</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" className="btn" disabled={revoke.isPending} onClick={() => revoke.mutate()}
              style={{ color: 'var(--rose)', borderColor: 'rgba(244,63,94,.35)' }}>
              {revoke.isPending ? 'Revoking…' : approved ? 'Revoke' : 'Withdraw'}
            </button>
            <button type="button" className="btn" onClick={() => setConfirming(false)}>Cancel</button>
          </div>
        </div>
      )}
      {revoke.isError && <div className="msg msg-error" role="alert">{(revoke.error as Error).message}</div>}
    </li>
  )
}

/**
 * The storage reserved for a dataset, and — for a platform admin while a delivery can still write —
 * raising it. The remedy when Curator refuses a delivery that cannot fit. Raise-only: the server
 * refuses anything at or below the current reservation.
 */
function Storage({ ds, isAdmin }: { ds: LabDataset; isAdmin: boolean }) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState('')
  const bytes = gibToBytes(value)
  const raise = useMutation({
    mutationFn: () => api.raiseDatasetStorage(ds.id, bytes!),
    onSuccess: () => {
      setEditing(false)
      setValue('')
      qc.invalidateQueries({ queryKey: ['lab-datasets'] })
    },
  })
  // A first limit only before delivery: on a bucket already filling, it could land below what it
  // holds and stop the delivery (the server refuses it too). A raise is fine while delivering.
  const writable = ds.status === 'approved' || (ds.status === 'delivering' && !!ds.estimated_bytes)
  const tooSmall = bytes !== null && !!ds.estimated_bytes && bytes <= ds.estimated_bytes
  return (
    <div className="hint" style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
      <span>Storage: {ds.estimated_bytes ? `${formatGib(ds.estimated_bytes)} reserved` : 'no limit set'}</span>
      {isAdmin && writable && !editing && (
        <button type="button" className="btn" onClick={() => setEditing(true)}>Reserve more…</button>
      )}
      {isAdmin && ds.status === 'delivering' && !ds.estimated_bytes && (
        <span>A delivery is running, so a first limit can no longer be set safely.</span>
      )}
      {editing && (
        <>
          <input className="input" inputMode="decimal" aria-label={`New storage for ${ds.name} (GiB)`} value={value}
            onChange={e => setValue(e.target.value)} style={{ width: 100 }} />
          <span>GiB</span>
          <button type="button" className="btn btn-primary" disabled={bytes === null || tooSmall || raise.isPending}
            onClick={() => raise.mutate()}>{raise.isPending ? 'Saving…' : 'Reserve'}</button>
          <button type="button" className="btn" onClick={() => setEditing(false)}>Cancel</button>
          {tooSmall && <span>Storage can only be raised.</span>}
          {!ds.estimated_bytes && (
            <span style={{ flexBasis: '100%' }}>
              A first limit is accepted only while the bucket is empty. A delivery starting at this moment could
              still meet it: it then stops without sealing, and raising the limit and delivering again resumes it.
            </span>
          )}
        </>
      )}
      {raise.isError && <div className="msg msg-error" role="alert">{(raise.error as Error).message}</div>}
    </div>
  )
}

/**
 * The lab's datasets and which projects can read each — with the one action a lab PI needs here:
 * taking a project's access away. Revocation is deliberately one human (the owning lab's PI, or a
 * platform admin): the server's rule; this list is only shown to those who can use it.
 */
export function LabDatasets({ labId, isAdmin = false }: { labId: string; isAdmin?: boolean }) {
  const { data: datasets = [], isLoading } = useQuery({
    queryKey: ['lab-datasets', labId],
    queryFn: () => api.listLabDatasets(labId),
  })
  if (isLoading) return null
  return (
    <section style={{ marginTop: 28 }} aria-label="Lab datasets">
      <div style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', marginBottom: 12 }}>
        DATASETS ({datasets.length})
      </div>
      {datasets.length === 0 && <div className="hint">No dataset has been requested in this lab yet.</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {datasets.map(ds => {
          const live = ds.grants.filter(g => !g.revoked_at)
          const revoked = ds.grants.filter(g => g.revoked_at)
          return (
            <div key={ds.id} className="card" style={{ padding: '14px 20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <b>{ds.name}</b>{ds.modality && <span className="chip">{ds.modality}</span>}
                <span className="hint">{ds.status}{ds.retention_until ? ` · retention until ${ds.retention_until}` : ''}</span>
              </div>
              <DatasetId id={ds.id} />
              <Storage ds={ds} isAdmin={isAdmin} />
              {live.length === 0
                ? <div className="hint" style={{ marginTop: 6 }}>Not shared with any project.</div>
                : <ul style={{ listStyle: 'none', margin: '6px 0 0', padding: 0 }}>{live.map(g => <GrantRow key={g.id} ds={ds} grant={g} />)}</ul>}
              {revoked.length > 0 && (
                <div className="hint" style={{ marginTop: 6 }}>
                  Revoked: {revoked.map(g => `${g.project_name || g.project_id} (${g.revoked_at!.slice(0, 10)})`).join(', ')}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
