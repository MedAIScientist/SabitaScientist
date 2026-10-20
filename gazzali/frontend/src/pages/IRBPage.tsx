import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { api, IRB_, Lab, Project } from '../api'
import { useAuth } from '../auth'
import {
  STATUS_TONE, appendNote, approvalBlockers, canWriteFor, irbActions, isLapsed, parseDocuments, todayUtc,
  type IrbAction,
} from '../components/irb/irbModel'

const card: React.CSSProperties = { background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 18px', marginBottom: 8 }
const panel: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)' }
const row: React.CSSProperties = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }
const danger: React.CSSProperties = { color: '#f43f5e' }

const ACTION_LABEL: Record<IrbAction, string> = {
  submit: 'Submit for review', withdraw: 'Withdraw', approve: 'Approve…', reject: 'Reject…',
  expire: 'Mark expired', close: 'Close',
}

export function IRBPage() {
  const qc = useQueryClient()
  const { isAdmin, username } = useAuth()
  const today = todayUtc()
  const { data: irbs = [], isError, error } = useQuery({ queryKey: ['irbs'], queryFn: () => api.listIrbs() })
  const { data: projects = [] } = useQuery<Project[]>({ queryKey: ['projects'], queryFn: () => api.listProjects() })
  const { data: labs = [] } = useQuery<Lab[]>({ queryKey: ['labs'], queryFn: () => api.listLabs() })
  const [params] = useSearchParams()
  const [showForm, setShowForm] = useState(params.has('project'))

  const who = { isAdmin, username }
  const writable = projects.filter(p => canWriteFor(p.id, who, projects, labs))
  // The admin's work first: records waiting on a decision rise to the top.
  const ordered = [...irbs].sort((a, b) => Number(b.status === 'submitted') - Number(a.status === 'submitted'))
  const waiting = irbs.filter(i => i.status === 'submitted').length

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', padding: '32px 28px', maxWidth: 1100, margin: '0 auto' }}>
      <h1 style={{ margin: '0 0 8px', fontSize: 24, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>IRB / Ethics Approvals</h1>
      <p className="hint" style={{ margin: '0 0 20px' }}>
        A project writes its ethics record and submits it with the committee's decision; a platform admin approves or rejects it.
        {isAdmin && waiting > 0 && <b> {waiting} awaiting your decision.</b>}
      </p>
      <button onClick={() => setShowForm(f => !f)} className="btn btn-primary">+ New ethics record</button>
      {showForm && (
        <CreateForm
          projects={writable}
          initialProject={params.get('project') ?? ''}
          onDone={() => { setShowForm(false); qc.invalidateQueries({ queryKey: ['irbs'] }) }}
        />
      )}
      {isError && <div className="msg msg-error" role="alert" style={{ marginTop: 16 }}>Could not load ethics records: {(error as Error).message}</div>}
      <div style={{ marginTop: 16 }}>
        {ordered.map(i => (
          <IrbCard
            key={i.id}
            irb={i}
            today={today}
            isAdmin={isAdmin}
            canWrite={canWriteFor(i.project_id, who, projects, labs)}
            projectName={projects.find(p => p.id === i.project_id)?.name}
          />
        ))}
      </div>
    </div>
  )
}

function CreateForm({ projects, initialProject, onDone }: { projects: Project[]; initialProject: string; onDone: () => void }) {
  const [chosen, setProjectId] = useState(initialProject)
  // Projects arrive after the first render; only a project the viewer can write
  // counts as chosen, so a stale or foreign ?project= never reaches the server.
  const projectId = projects.some(p => p.id === chosen) ? chosen : ''
  const [title, setTitle] = useState('')
  const [institution, setInstitution] = useState('')
  const [protocolNumber, setProtocolNumber] = useState('')
  const create = useMutation({
    mutationFn: () => api.createIrb({ project_id: projectId, title, institution, protocol_number: protocolNumber }),
    onSuccess: onDone,
  })
  if (projects.length === 0) {
    return <p className="hint" style={{ marginTop: 12 }}>You can add an ethics record to a project you own or edit, or one in a lab you lead.</p>
  }
  return (
    <form
      aria-label="New ethics record"
      onSubmit={e => { e.preventDefault(); if (projectId) create.mutate() }}
      style={{ display: 'flex', flexDirection: 'column', gap: 10, margin: '12px 0 16px', background: 'var(--surface-card)', border: '1px solid rgba(var(--accent-rgb),0.2)', borderRadius: 10, padding: 20 }}
    >
      <label className="field"><span>Project</span>
        <select className="input" value={projectId} onChange={e => setProjectId(e.target.value)} required>
          <option value="">Choose a project…</option>
          {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </label>
      <label className="field"><span>Protocol title</span>
        <input className="input" value={title} onChange={e => setTitle(e.target.value)} required />
      </label>
      <div style={row}>
        <label className="field"><span>Institution</span>
          <input className="input" value={institution} onChange={e => setInstitution(e.target.value)} required />
        </label>
        <label className="field"><span>Protocol number</span>
          <input className="input" value={protocolNumber} onChange={e => setProtocolNumber(e.target.value)} required />
        </label>
      </div>
      <p className="hint" style={{ margin: 0 }}>It is saved as a draft. Submit it for review from the list once you have the committee's decision.</p>
      {create.isError && <div className="msg msg-error" role="alert">{(create.error as Error).message}</div>}
      <button type="submit" className="btn btn-primary" disabled={!projectId || create.isPending}>Save draft</button>
    </form>
  )
}

function IrbCard({ irb, today, isAdmin, canWrite, projectName }: {
  irb: IRB_; today: string; isAdmin: boolean; canWrite: boolean; projectName?: string
}) {
  const qc = useQueryClient()
  const [open, setOpen] = useState<IrbAction | null>(null)
  const update = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.updateIrb(irb.id, body),
    onSuccess: () => {
      setOpen(null)
      qc.invalidateQueries({ queryKey: ['irbs'] })
      qc.invalidateQueries({ queryKey: ['imaging-inbox'] })  // an approval can unblock "Approve & release"
    },
  })
  const tone = STATUS_TONE[irb.status] ?? { label: irb.status.toUpperCase(), color: 'var(--text-dim)' }
  const lapsed = isLapsed(irb, today)
  const actions = irbActions(irb, { isAdmin, canWrite })
  const docs = irb.documents ?? []

  function act(a: IrbAction) {
    update.reset()
    if (a === 'withdraw') update.mutate({ status: 'draft' })
    else setOpen(open === a ? null : a)
  }

  return (
    <div style={card} data-testid={`irb-${irb.id}`}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-heading)' }}>{irb.title}</div>
          <div style={{ fontSize: 14, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
            {projectName ?? irb.project_id ?? '—'} · {irb.institution} · {irb.protocol_number}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'flex-start' }}>
          {lapsed && <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)', ...danger, padding: '2px 7px', borderRadius: 3, background: 'var(--surface-input)' }}>LAPSED</span>}
          <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)', color: tone.color, padding: '2px 7px', borderRadius: 3, background: 'var(--surface-input)' }}>{tone.label}</span>
        </div>
      </div>

      <dl style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 18px', margin: '8px 0 0', fontSize: 13.5, color: 'var(--text-2)' }}>
        {irb.approval_date && <div><dt style={{ display: 'inline' }}>Committee decision: </dt><dd style={{ display: 'inline', margin: 0 }}>{irb.approval_date}</dd></div>}
        {irb.expiry_date && <div><dt style={{ display: 'inline' }}>Valid until: </dt><dd style={{ display: 'inline', margin: 0 }}>{irb.expiry_date}</dd></div>}
        {irb.approved_at && <div><dt style={{ display: 'inline' }}>Approved on Medai: </dt><dd style={{ display: 'inline', margin: 0 }}>{irb.approved_at.slice(0, 10)}</dd></div>}
        {docs.length > 0 && <div><dt style={{ display: 'inline' }}>Documents: </dt><dd style={{ display: 'inline', margin: 0 }}>{docs.join(' · ')}</dd></div>}
      </dl>
      {irb.notes && <p style={{ whiteSpace: 'pre-wrap', fontSize: 13.5, color: 'var(--text-2)', margin: '8px 0 0' }}>{irb.notes}</p>}
      {lapsed && <p className="hint" style={{ ...danger, margin: '8px 0 0' }}>This approval's validity date has passed. Datasets that rely on it can no longer be approved until it is renewed.</p>}

      {actions.length > 0 && (
        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
          {actions.map(a => (
            <button key={a} type="button" className="btn" style={a === 'reject' || a === 'expire' ? danger : undefined}
              disabled={update.isPending} onClick={() => act(a)}>
              {irb.status !== 'draft' && a === 'submit' ? 'Resubmit for review' : ACTION_LABEL[a]}
            </button>
          ))}
        </div>
      )}

      {(open === 'submit' || open === 'approve') && (
        <EvidenceForm irb={irb} today={today} mode={open} pending={update.isPending}
          onSend={ev => update.mutate({ status: open === 'submit' ? 'submitted' : 'approved', ...ev })} />
      )}
      {open === 'reject' && <RejectForm pending={update.isPending}
        onSend={reason => update.mutate({ status: 'rejected', notes: appendNote(irb.notes, `Rejected ${today}: ${reason}`) })} />}
      {(open === 'expire' || open === 'close') && (
        <div style={panel}>
          <p className="hint" style={{ margin: 0 }}>
            {open === 'expire' ? 'Mark this approval as expired?' : 'Close this record? It cannot be reopened from this page.'}{' '}
            {irb.status === 'approved' && 'Datasets already approved under it keep their access — revoke those separately.'}
          </p>
          <div><button type="button" className="btn" style={danger} disabled={update.isPending}
            onClick={() => update.mutate({ status: open === 'expire' ? 'expired' : 'closed' })}>
            Yes, {open === 'expire' ? 'mark expired' : 'close'}
          </button></div>
        </div>
      )}
      {update.isError && <div className="msg msg-error" role="alert" style={{ marginTop: 10 }}>{(update.error as Error).message}</div>}
    </div>
  )
}

/** The committee decision: the same three facts the server requires to approve. A
 *  writer supplies them on submit so the admin can approve without retyping. */
function EvidenceForm({ irb, today, mode, pending, onSend }: {
  irb: IRB_; today: string; mode: 'submit' | 'approve'; pending: boolean
  onSend: (ev: { approval_date: string; expiry_date: string; documents: string[] }) => void
}) {
  const [approvalDate, setApprovalDate] = useState(irb.approval_date ?? '')
  const [expiryDate, setExpiryDate] = useState(irb.expiry_date ?? '')
  const [docsText, setDocsText] = useState((irb.documents ?? []).join('\n'))
  const ev = { approval_date: approvalDate, expiry_date: expiryDate, documents: parseDocuments(docsText) }
  const blockers = approvalBlockers(ev, today)
  return (
    <form style={panel} aria-label={mode === 'submit' ? 'Submit for review' : 'Approve'}
      onSubmit={e => { e.preventDefault(); if (blockers.length === 0) onSend(ev) }}>
      <div style={row}>
        <label className="field"><span>Committee decision date</span>
          <input className="input" type="date" value={approvalDate} onChange={e => setApprovalDate(e.target.value)} />
        </label>
        <label className="field"><span>Valid until</span>
          <input className="input" type="date" value={expiryDate} onChange={e => setExpiryDate(e.target.value)} />
        </label>
      </div>
      <label className="field"><span>Document references (one per line)</span>
        <textarea className="input" rows={3} value={docsText} onChange={e => setDocsText(e.target.value)}
          placeholder="Committee decision number and date, or the hospital document number / verification code" />
      </label>
      {blockers.length > 0 && <ul className="hint" style={{ margin: 0, paddingLeft: 18 }}>{blockers.map(b => <li key={b}>{b}</li>)}</ul>}
      <div><button type="submit" className="btn btn-primary" disabled={pending || blockers.length > 0}>
        {mode === 'submit' ? 'Submit for review' : 'Approve'}
      </button></div>
    </form>
  )
}

function RejectForm({ pending, onSend }: { pending: boolean; onSend: (reason: string) => void }) {
  const [reason, setReason] = useState('')
  return (
    <form style={panel} aria-label="Reject" onSubmit={e => { e.preventDefault(); if (reason.trim()) onSend(reason.trim()) }}>
      <label className="field"><span>Reason (shown to the project)</span>
        <textarea className="input" rows={2} value={reason} onChange={e => setReason(e.target.value)} />
      </label>
      <div><button type="submit" className="btn" style={danger} disabled={pending || !reason.trim()}>Reject</button></div>
    </form>
  )
}
