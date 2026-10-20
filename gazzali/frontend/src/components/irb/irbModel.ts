import type { IRB_, Lab, Project } from '../../api'

// Pure rules for the IRB page. The backend (api/routes/irb.py) is the authority —
// these only decide which controls to OFFER, so nobody is shown a button the
// server will refuse, and a decision form can't be sent while it would bounce.

export type IrbAction = 'submit' | 'withdraw' | 'approve' | 'reject' | 'expire' | 'close'

export interface Viewer {
  isAdmin: boolean
  /** Project owner/editor, the project's lab pi/admin, or a platform admin. */
  canWrite: boolean
}

/** Mirrors irb.py `_may_write_irb`: platform admin, project owner/editor, or the
 *  pi/admin of the project's lab. Only projects the viewer belongs to are known
 *  here (GET /projects lists memberships), so a lab PI outside the project's team
 *  is not offered the buttons — the server stays the final word either way. */
export function canWriteFor(
  projectId: string | undefined,
  who: { isAdmin: boolean; username: string | null },
  projects: Project[],
  labs: Lab[],
): boolean {
  if (who.isAdmin) return true
  const project = projects.find(p => p.id === projectId)
  if (!project || !who.username) return false
  const mine = project.members.find(m => m.username === who.username)
  if (mine && (mine.role === 'owner' || mine.role === 'editor')) return true
  const lab = project.lab_id ? labs.find(l => l.id === project.lab_id) : undefined
  const inLab = lab?.members.find(m => m.username === who.username)
  return !!inLab && (inLab.role === 'pi' || inLab.role === 'admin')
}

/** Today as YYYY-MM-DD in UTC — the same clock the server compares against. */
export function todayUtc(now: Date = new Date()): string {
  return now.toISOString().slice(0, 10)
}

/** An approved record whose expiry date has passed. The server never flips it to
 *  'expired' on its own, so the page has to say so. */
export function isLapsed(irb: Pick<IRB_, 'status' | 'expiry_date'>, today: string): boolean {
  return irb.status === 'approved' && !!irb.expiry_date && irb.expiry_date <= today
}

export function irbActions(irb: Pick<IRB_, 'status'>, viewer: Viewer): IrbAction[] {
  const out: IrbAction[] = []
  switch (irb.status) {
    case 'draft':
    case 'rejected':
    case 'expired':
      if (viewer.canWrite) out.push('submit', 'close')
      break
    case 'submitted':
      if (viewer.canWrite) out.push('withdraw')
      if (viewer.isAdmin) out.push('approve', 'reject')
      break
    case 'approved':
      // Sealed record: only an admin may end it, and only by status.
      if (viewer.isAdmin) out.push('expire', 'close')
      break
    // 'closed' is terminal in this UI.
  }
  return out
}

export interface Evidence {
  approval_date: string
  expiry_date: string
  documents: string[]
}

/** Split the documents textarea into references, one per line, blanks dropped. */
export function parseDocuments(text: string): string[] {
  return text.split('\n').map(s => s.trim()).filter(Boolean)
}

/** Why an approval would be refused, mirroring irb.py's checks. Empty = sendable. */
export function approvalBlockers(ev: Evidence, today: string): string[] {
  const out: string[] = []
  if (!ev.approval_date) out.push('Enter the committee decision date.')
  if (!ev.expiry_date) out.push('Enter the date the approval is valid until.')
  else if (ev.expiry_date <= today) out.push('The approval must still be valid after today.')
  if (ev.documents.length === 0) out.push('Add at least one document reference.')
  return out
}

/** The server overwrites notes, so a rejection reason is appended by the client. */
export function appendNote(existing: string | null | undefined, line: string): string {
  const prior = (existing ?? '').trim()
  return prior ? `${prior}\n\n${line}` : line
}

export const STATUS_TONE: Record<string, { label: string; color: string }> = {
  draft: { label: 'DRAFT', color: 'var(--text-dim)' },
  submitted: { label: 'AWAITING DECISION', color: '#f59e0b' },
  approved: { label: 'APPROVED', color: '#10b981' },
  rejected: { label: 'REJECTED', color: '#f43f5e' },
  expired: { label: 'EXPIRED', color: '#f43f5e' },
  closed: { label: 'CLOSED', color: 'var(--text-dim)' },
}
