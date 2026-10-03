import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ResearchMode } from '../../api'
import { UsageMeter } from './UsageMeter'

const MODES: { value: ResearchMode; label: string; who: string }[] = [
  { value: 'co-pilot', label: 'CoPilot (recommended)', who: 'You review the design; a PI of the lab reviews the results and the final paper.' },
  { value: 'gate-only', label: 'Gate-only', who: 'Three checkpoints: paper screening, experiment design, final quality.' },
  { value: 'step-by-step', label: 'Step-by-step', who: 'You approve every stage (slow; the paper found it adds little).' },
  { value: 'full-auto', label: 'Full-auto', who: 'No human input (lowest quality in the paper’s study).' },
]

type Step = 1 | 2 | 3

/** Question → data → review. Every step can be revisited; nothing starts before step 3. */
export function StartRunWizard({ projectId, experimentId, hypothesis, onStarted }: {
  projectId: string; experimentId: string; hypothesis?: string | null; onStarted?: () => void
}) {
  const qc = useQueryClient()
  const [step, setStep] = useState<Step>(1)
  const [topic, setTopic] = useState(hypothesis ?? '')
  const [domain, setDomain] = useState('')
  const [mode, setMode] = useState<ResearchMode>('co-pilot')
  const [datasetId, setDatasetId] = useState('')
  const [irbId, setIrbId] = useState('')
  const { data: domains = [] } = useQuery({ queryKey: ['research-domains'], queryFn: api.researchDomains })
  const { data: datasets = [] } = useQuery({
    queryKey: ['research-datasets', projectId], queryFn: () => api.researchDatasets(projectId), enabled: step >= 2,
  })
  const check = useMutation({ mutationFn: () => api.researchTopicCheck(topic, domain || undefined) })
  const start = useMutation({
    mutationFn: () => api.startResearchRun(projectId, experimentId, {
      topic, mode, ...(domain ? { domain } : {}), ...(datasetId ? { dataset_id: datasetId, irb_id: irbId } : {}),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['research-runs', experimentId] })
      qc.invalidateQueries({ queryKey: ['research-usage'] })
      setStep(1)
      onStarted?.()
    },
  })
  const dataset = datasets.find(d => d.id === datasetId)
  const topicOk = topic.trim().length >= 10
  const score = check.data

  const stepHeader = (n: Step, label: string) => (
    <button type="button" onClick={() => (n < step || (n === 2 && topicOk) || (n === 3 && topicOk && (!datasetId || irbId))) && setStep(n)}
      aria-current={step === n ? 'step' : undefined}
      style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: step === n ? 700 : 400,
        color: step === n ? 'var(--accent)' : 'var(--text-3)', padding: 0 }}>
      {n}. {label}
    </button>
  )

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 14 }}>
      <div style={{ display: 'flex', gap: 16, marginBottom: 12 }} aria-label="Steps">
        {stepHeader(1, 'Question')}{stepHeader(2, 'Data')}{stepHeader(3, 'Review & start')}
      </div>

      {step === 1 && (
        <div style={{ display: 'grid', gap: 8 }}>
          <label className="field">
            <span>Research question</span>
            <textarea className="input" rows={3} value={topic} onChange={e => setTopic(e.target.value)}
              placeholder="e.g. Does class weighting improve minority-class recall of logistic regression?" />
          </label>
          <label className="field">
            <span>Kind of study</span>
            <select className="input" value={domain} onChange={e => setDomain(e.target.value)}>
              <option value="">General</option>
              {domains.map(d => <option key={d.id} value={d.id}>{d.label}</option>)}
            </select>
          </label>
          {domain && <p style={{ fontSize: 13, color: 'var(--text-3)', margin: 0 }}>{domains.find(d => d.id === domain)?.guidance}</p>}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button className="btn" disabled={!topicOk || check.isPending} onClick={() => check.mutate()}>
              {check.isPending ? 'Checking…' : 'Check my question'}
            </button>
            <button className="btn btn-primary" disabled={!topicOk} onClick={() => setStep(2)}>Next: data</button>
          </div>
          {score && (
            <div role="status" style={{ fontSize: 13, padding: 8, borderRadius: 6, background: 'var(--surface-input)' }}>
              <b>Score {score.overall}/10</b> · novelty {score.novelty} · specificity {score.specificity} · feasibility {score.feasibility}
              {score.suggestion && <div style={{ marginTop: 4 }}>Suggestion: {score.suggestion}</div>}
            </div>
          )}
          {check.isError && <div className="msg msg-error" role="alert">{(check.error as Error).message}</div>}
        </div>
      )}

      {step === 2 && (
        <div style={{ display: 'grid', gap: 8 }}>
          <label className="field">
            <span>Dataset</span>
            <select className="input" value={datasetId} onChange={e => {
              const d = datasets.find(x => x.id === e.target.value)
              setDatasetId(e.target.value)
              setIrbId(d && d.irb_ids.length === 1 ? d.irb_ids[0] : '')
            }}>
              <option value="">No dataset: public data the run finds itself</option>
              {datasets.map(d => <option key={d.id} value={d.id}>{d.name}{d.modality ? ` (${d.modality})` : ''}</option>)}
            </select>
          </label>
          {datasets.length === 0 && (
            <p style={{ fontSize: 13, color: 'var(--text-3)', margin: 0 }}>
              Patient datasets appear here once they are approved for your lab and covered by an active IRB of this project.
            </p>
          )}
          {dataset && dataset.irb_ids.length > 1 && (
            <label className="field">
              <span>IRB approval that covers it</span>
              <select className="input" value={irbId} onChange={e => setIrbId(e.target.value)}>
                <option value="">Choose…</option>
                {dataset.irb_ids.map(i => <option key={i} value={i}>{i}</option>)}
              </select>
            </label>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn" onClick={() => setStep(1)}>Back</button>
            <button className="btn btn-primary" disabled={!!datasetId && !irbId} onClick={() => setStep(3)}>Next: review</button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div style={{ display: 'grid', gap: 10 }}>
          <fieldset style={{ border: 'none', padding: 0, margin: 0, display: 'grid', gap: 6 }}>
            <legend style={{ fontWeight: 600, marginBottom: 4 }}>How involved do you want to be?</legend>
            {MODES.map(m => (
              <label key={m.value} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', cursor: 'pointer' }}>
                <input type="radio" name="mode" checked={mode === m.value} onChange={() => setMode(m.value)} />
                <span><b>{m.label}</b><br /><span style={{ fontSize: 13, color: 'var(--text-3)' }}>{m.who}</span></span>
              </label>
            ))}
          </fieldset>
          <div style={{ fontSize: 13, padding: 8, borderRadius: 6, background: 'var(--surface-input)' }}>
            <div><b>Question:</b> {topic}</div>
            <div><b>Data:</b> {dataset ? `${dataset.name} (IRB ${irbId})` : 'public data only'}</div>
            <div><b>Runs on:</b> the server’s CPU. In our test the discovery phase (stages 1–9) took about 10 minutes; experiments and writing take longer.</div>
          </div>
          <UsageMeter />
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn" onClick={() => setStep(2)}>Back</button>
            <button className="btn btn-primary" disabled={start.isPending} onClick={() => start.mutate()}>
              {start.isPending ? 'Starting…' : 'Start the run'}
            </button>
          </div>
          {start.isError && <div className="msg msg-error" role="alert">{(start.error as Error).message}</div>}
        </div>
      )}
    </div>
  )
}
