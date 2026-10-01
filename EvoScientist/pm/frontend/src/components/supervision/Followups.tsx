import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Followup, supervisionApi } from '../../api'

function age(f: Followup): string {
  if (f.weeks_open === 0) return 'asked this week'
  return `asked ${f.weeks_open} week${f.weeks_open === 1 ? '' : 's'} ago`
}

function Meta({ f }: { f: Followup }) {
  return (
    <span className="job-meta">
      {age(f)}
      {f.due_date && <> · due {f.due_date}</>}
      {f.overdue && <b style={{ color: 'var(--rose)' }}> · overdue</b>}
    </span>
  )
}

/** The student's open requests from their supervisor, answered inside the weekly update. */
export function StudentFollowups() {
  const qc = useQueryClient()
  const { data: items = [] } = useQuery({
    queryKey: ['followups', 'mine', 'open'],
    queryFn: () => supervisionApi.listFollowups({ status: 'open' }),
  })
  const [notes, setNotes] = useState<Record<string, string>>({})
  const save = useMutation({
    mutationFn: ({ f, done }: { f: Followup; done: boolean }) =>
      supervisionApi.updateFollowup(f.id, { status: done ? 'done' : 'open', note: notes[f.id] ?? f.student_note ?? undefined }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['followups'] }),
  })
  if (items.length === 0) return null
  return (
    <section style={{ marginBottom: 22 }} aria-label="From your supervisor">
      <h2 className="section-title">From your supervisor <span className="count">{items.length}</span></h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {items.map(f => (
          <div key={f.id} className="inbox-item" style={{ borderLeftColor: f.overdue ? 'var(--rose)' : undefined }}>
            <div className="request-title">{f.text}</div>
            <Meta f={f} />
            <input className="input" placeholder="Note for your supervisor (optional) — what you did, or why not yet"
              value={notes[f.id] ?? f.student_note ?? ''} onChange={e => setNotes(n => ({ ...n, [f.id]: e.target.value }))} />
            <div className="inbox-actions">
              <button className="btn" disabled={save.isPending} onClick={() => save.mutate({ f, done: false })}>Not yet — save note</button>
              <button className="btn btn-primary" disabled={save.isPending} onClick={() => save.mutate({ f, done: true })}>Done</button>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

/** A student's still-open requests, shown to the supervisor next to the report being reviewed. */
export function OpenFollowups({ studentId }: { studentId: string }) {
  const qc = useQueryClient()
  const { data: items = [] } = useQuery({
    queryKey: ['followups', studentId, 'open'],
    queryFn: () => supervisionApi.listFollowups({ studentId, status: 'open' }),
  })
  const close = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'done' | 'dropped' }) => supervisionApi.updateFollowup(id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['followups'] }),
  })
  if (items.length === 0) return <p className="hint">No open follow-ups.</p>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {items.map(f => (
        <div key={f.id} className="job" data-state={f.overdue ? 'failed' : 'running'}>
          <div className="job-main">
            <div className="job-title" style={{ whiteSpace: 'normal' }}>{f.text}</div>
            <Meta f={f} />
            {f.student_note && <div className="job-meta">Student: “{f.student_note}”</div>}
          </div>
          <button className="btn" style={{ height: 28 }} onClick={() => close.mutate({ id: f.id, status: 'done' })}>Mark done</button>
          <button className="btn" style={{ height: 28 }} onClick={() => close.mutate({ id: f.id, status: 'dropped' })}>Drop</button>
        </div>
      ))}
    </div>
  )
}

export type DraftFollowup = { text: string; due_date: string }

/** New requests added while reviewing; each becomes a tracked follow-up. */
export function FollowupEditor({ value, onChange }: { value: DraftFollowup[]; onChange: (v: DraftFollowup[]) => void }) {
  const set = (i: number, patch: Partial<DraftFollowup>) => onChange(value.map((f, j) => (j === i ? { ...f, ...patch } : f)))
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {value.map((f, i) => (
        <div key={i} style={{ display: 'flex', gap: 6 }}>
          <input className="input" placeholder="What should the student do?" value={f.text} onChange={e => set(i, { text: e.target.value })} />
          <input className="input" type="date" value={f.due_date} onChange={e => set(i, { due_date: e.target.value })} style={{ width: 150 }} title="Due date (optional)" />
          <button className="icon-btn" aria-label="Remove" onClick={() => onChange(value.filter((_, j) => j !== i))}>✕</button>
        </div>
      ))}
      <button className="btn" style={{ alignSelf: 'flex-start', height: 30 }} onClick={() => onChange([...value, { text: '', due_date: '' }])}>+ Add follow-up</button>
    </div>
  )
}
