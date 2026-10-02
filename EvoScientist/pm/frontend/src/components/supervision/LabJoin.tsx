import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, LabJoinRequest } from '../../api'
import { useAuth } from '../../auth'

/** A professor works only with the students of a lab they lead — no lab, no students. */
export function NoLabPrompt() {
  const { role, isAdmin } = useAuth()
  const navigate = useNavigate()
  const isProfessor = role === 'professor' && !isAdmin
  const { data: labs } = useQuery({ queryKey: ['labs'], queryFn: api.listLabs, enabled: isProfessor })
  // can_manage = the caller is this lab's PI or lab admin
  if (!isProfessor || !labs || labs.some(l => l.can_manage)) return null
  return (
    <section className="card" role="status" style={{ padding: 18, margin: '0 0 22px', borderColor: 'rgba(var(--accent-rgb),0.35)' }}>
      <h3 className="section-title" style={{ marginTop: 0 }}>Create your lab</h3>
      <p style={{ margin: '0 0 12px', color: 'var(--text-2)' }}>
        Your students are the members of the lab you lead. Create a lab — you become its PI — then students ask to join and you approve them.
      </p>
      <button className="btn btn-primary" onClick={() => navigate('/labs?new=1')}>Create a lab</button>
    </section>
  )
}

function Row({ req }: { req: LabJoinRequest }) {
  const qc = useQueryClient()
  const decide = useMutation({
    mutationFn: (d: 'approve' | 'decline') => api.decideLabJoinRequest(req.lab_id, req.id, d),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['lab-join-pending'] })
      qc.invalidateQueries({ queryKey: ['labs'] })
    },
  })
  return (
    <div className="inbox-item">
      <div className="inbox-kind">Wants to join {req.lab_name}</div>
      <div className="request-title">{req.username} <span className="chip">{req.lab_role.toUpperCase()}</span></div>
      {req.message && <p className="inbox-purpose">{req.message}</p>}
      <div className="inbox-actions">
        <button className="btn btn-primary" disabled={decide.isPending} onClick={() => decide.mutate('approve')}>Approve</button>
        <button className="btn" disabled={decide.isPending} onClick={() => decide.mutate('decline')}>Decline</button>
      </div>
      {decide.isError && <div className="msg msg-error" role="alert">{(decide.error as Error).message}</div>}
    </div>
  )
}

/** Students waiting to join a lab the signed-in user leads. Renders nothing when empty. */
export function JoinRequestsInbox() {
  const { data: items = [] } = useQuery({ queryKey: ['lab-join-pending'], queryFn: api.pendingLabJoinRequests, refetchInterval: 60_000 })
  if (items.length === 0) return null
  return (
    <section aria-label="Lab join requests" style={{ margin: '0 0 26px' }}>
      <h3 className="section-title">Asking to join your lab <span className="count">{items.length}</span></h3>
      <div className="inbox-grid">{items.map(r => <Row key={r.id} req={r} />)}</div>
    </section>
  )
}
