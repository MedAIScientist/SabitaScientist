import { useQuery } from '@tanstack/react-query'
import { api, DatasetRequest } from '../../api'

/** One request's progress: a row of steps and who has to act next. */
function Tracker({ req }: { req: DatasetRequest }) {
  const stopped = req.status === 'expired' || req.status === 'revoked'
  return (
    <div className="request">
      <div className="request-head">
        <div>
          <div className="request-title">{req.name}{req.modality && <span className="chip">{req.modality}</span>}</div>
          <div className="request-meta">
            {req.accession_count} stud{req.accession_count === 1 ? 'y' : 'ies'}
            {req.requested_by && ` · requested by ${req.requested_by}`}
            {` · ${new Date(req.created_at).toLocaleDateString()}`}
          </div>
        </div>
        <div className="request-next">
          {stopped ? <span className="warn">{req.status === 'revoked' ? 'Revoked' : 'Expired'}</span>
            : req.waiting_on ? <>Waiting on <b>{req.waiting_on}</b></>
            : <span className="ok">Ready to use</span>}
        </div>
      </div>
      <ol className="steps" aria-label="Progress">
        {req.steps.map(s => <li key={s.key} data-state={stopped ? 'todo' : s.state}>{s.label}</li>)}
      </ol>
    </div>
  )
}

/** Imaging-data requests made for this project, newest first. */
export function DatasetRequests({ projectId }: { projectId: string }) {
  const { data: requests = [] } = useQuery({
    queryKey: ['dataset-requests', projectId],
    queryFn: () => api.listDatasetRequests(projectId),
  })
  if (requests.length === 0) return null
  return (
    <section style={{ marginBottom: 28 }}>
      <h3 className="section-title">Data requests</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {requests.map(r => <Tracker key={r.id} req={r} />)}
      </div>
    </section>
  )
}
