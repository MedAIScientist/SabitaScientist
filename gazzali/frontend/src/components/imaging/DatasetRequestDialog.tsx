import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, IRB_, Project } from '../../api'

const MODALITIES = ['CT', 'MR', 'DX', 'CR', 'US', 'MG', 'PT', 'NM', 'XA', 'OT']
const SOON_DAYS = 60

function daysUntil(date: string | null): number | null {
  if (!date) return null
  return Math.ceil((new Date(date).getTime() - Date.now()) / 86_400_000)
}

/** Why an IRB would hold the request up later, said now. */
function irbWarning(irb: IRB_): string | null {
  if (irb.status !== 'approved') return `status is “${irb.status}” — the admin step needs an approved IRB`
  const d = daysUntil(irb.expiry_date)
  if (d === null) return 'no expiry date — the admin step needs one'
  if (d <= 0) return 'expired'
  if (d <= SOON_DAYS) return `expires in ${d} days`
  return null
}

/**
 * Ask for imaging data for this project. Creates a draft dataset owned by a lab;
 * the lab PI and then a platform admin approve it (see the approvals inbox), and
 * the request's progress shows on the project's Data tab.
 */
export function DatasetRequestDialog({ project, onClose }: { project: Project; onClose: () => void }) {
  const qc = useQueryClient()
  const { data: irbs = [] } = useQuery({ queryKey: ['irbs', project.id], queryFn: () => api.listIrbs(project.id) })
  const { data: labs = [] } = useQuery({ queryKey: ['labs'], queryFn: api.listLabs })
  // Datasets belong to a lab you are in; the API rejects any other.
  const myLabs = labs.filter(l => l.members.length > 0 || l.can_manage)

  const [name, setName] = useState('')
  const [purpose, setPurpose] = useState('')
  const [modality, setModality] = useState('')
  const [labId, setLabId] = useState(project.lab_id ?? '')
  const [accessions, setAccessions] = useState('')
  const [irbIds, setIrbIds] = useState<string[]>([])
  const [renders, setRenders] = useState(true)

  const accessionList = useMemo(
    () => [...new Set(accessions.split(/[\s,;]+/).map(a => a.trim()).filter(Boolean))],
    [accessions],
  )
  const effectiveLab = labId || (myLabs.length === 1 ? myLabs[0].id : '')
  const ready = name.trim() && purpose.trim() && effectiveLab && accessionList.length > 0

  const create = useMutation({
    mutationFn: () => api.requestDataset({
      name: name.trim(), purpose: purpose.trim(), lab_id: effectiveLab, project_id: project.id,
      modality: modality || undefined, accession_list: accessionList, irb_ids: irbIds, renders,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dataset-requests', project.id] })
      qc.invalidateQueries({ queryKey: ['imaging-inbox'] })
      onClose()
    },
  })

  return (
    <div className="palette-scrim" onMouseDown={onClose}>
      <form className="dialog" role="dialog" aria-label="Request imaging data"
        onMouseDown={e => e.stopPropagation()}
        onSubmit={e => { e.preventDefault(); if (ready) create.mutate() }}>
        <header>
          <h2>Request imaging data</h2>
          <p>For <b>{project.name}</b>. The lab PI and then a platform admin approve it; you can follow each step on the Data tab.</p>
        </header>

        <label className="field"><span>Dataset name</span>
          <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Knee MR 2019–2024" autoFocus />
        </label>
        <label className="field"><span>Purpose</span>
          <textarea className="input" rows={2} value={purpose} onChange={e => setPurpose(e.target.value)}
            placeholder="What the data is for — reviewers read this." />
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <label className="field"><span>Modality</span>
            <select className="input" value={modality} onChange={e => setModality(e.target.value)}>
              <option value="">Mixed / not sure</option>
              {MODALITIES.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </label>
          <label className="field"><span>Owning lab</span>
            <select className="input" value={effectiveLab} onChange={e => setLabId(e.target.value)}>
              <option value="">Choose a lab…</option>
              {myLabs.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          </label>
        </div>
        <label className="field">
          <span>Accession numbers <em style={{ fontStyle: 'normal', color: 'var(--text-3)' }}>({accessionList.length})</em></span>
          <textarea className="input" rows={4} value={accessions} onChange={e => setAccessions(e.target.value)}
            placeholder="One per line, or separated by commas. Tip: export the list from Curator (PACS)." style={{ fontFamily: 'var(--font-code)' }} />
        </label>

        <fieldset className="field">
          <span>Ethics (IRB) approvals</span>
          {irbs.length === 0 && (
            <p className="hint">This project has no IRB record yet. Add one on the Ethics (IRB) page — the request cannot be approved without it.</p>
          )}
          {irbs.map(irb => {
            const warn = irbWarning(irb)
            return (
              <label key={irb.id} className="check">
                <input type="checkbox" checked={irbIds.includes(irb.id)}
                  onChange={e => setIrbIds(ids => e.target.checked ? [...ids, irb.id] : ids.filter(i => i !== irb.id))} />
                <span>{irb.title} <small>{irb.protocol_number}</small>
                  {warn && <small className="warn"> — {warn}</small>}</span>
              </label>
            )
          })}
          {irbs.length > 0 && irbIds.length === 0 && <p className="hint">Select at least one: the PI cannot approve a request without an IRB.</p>}
        </fieldset>

        <label className="check">
          <input type="checkbox" checked={renders} onChange={e => setRenders(e.target.checked)} />
          <span>Also create viewable images <small>(needed to annotate in CVAT; uses extra storage)</small></span>
        </label>

        {create.isError && <div className="msg msg-error" role="alert">{(create.error as Error).message}</div>}
        <footer>
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={!ready || create.isPending}>
            {create.isPending ? 'Sending…' : 'Send request'}
          </button>
        </footer>
      </form>
    </div>
  )
}
