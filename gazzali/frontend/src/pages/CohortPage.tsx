import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ProjectHeader } from '../components/ProjectHeader'
import {
  api,
  cohortApi,
  type CohortAnalysis,
  type CohortAnalysisRequest,
  type CohortMethod,
  type CohortFlow,
  type CohortPopulation,
  type CohortQuality,
  type CohortRenderedTable,
  type CohortTrace,
} from '../api'

const ACCENT = '#ff8015'
const ACCENT_RGB = '255,128,21'

type Tab = 'data' | 'population' | 'analysis' | 'quality' | 'provenance' | 'report'

const TABS: { key: Tab; label: string }[] = [
  { key: 'data', label: 'Data' },
  { key: 'population', label: 'Population' },
  { key: 'analysis', label: 'Analysis' },
  { key: 'quality', label: 'Quality' },
  { key: 'provenance', label: 'Provenance' },
  { key: 'report', label: 'Report' },
]

const card: React.CSSProperties = {
  background: 'var(--surface, #fff)',
  border: '1px solid var(--border, #e5e7eb)',
  borderRadius: 10,
  padding: 16,
  marginBottom: 16,
}
const label: React.CSSProperties = { fontSize: 12, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '.04em' }
const muted: React.CSSProperties = { color: '#6b7280', fontSize: 13 }
const button = (primary = false): React.CSSProperties => ({
  padding: '7px 14px',
  borderRadius: 8,
  border: primary ? 'none' : '1px solid var(--border, #d1d5db)',
  background: primary ? ACCENT : 'transparent',
  color: primary ? '#fff' : 'inherit',
  fontWeight: 600,
  fontSize: 13,
  cursor: 'pointer',
})
const input: React.CSSProperties = {
  padding: '7px 10px',
  borderRadius: 8,
  border: '1px solid var(--border, #d1d5db)',
  fontSize: 13,
  width: '100%',
}
const th: React.CSSProperties = { textAlign: 'left', padding: '6px 10px', borderBottom: '1px solid #e5e7eb', fontSize: 12, color: '#6b7280', verticalAlign: 'bottom' }
const td: React.CSSProperties = { padding: '6px 10px', borderBottom: '1px solid #f3f4f6', fontSize: 13 }

function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}

function pText(value: number | null | undefined): string {
  if (value === null || value === undefined) return '–'
  return value < 0.001 ? '<0.001' : value.toFixed(3)
}

function bandColor(band: string): string {
  if (band === 'excellent') return '#059669'
  if (band === 'good') return '#0ea5e9'
  if (band === 'fair') return '#d97706'
  return '#dc2626'
}

/** A labelled set of column checkboxes; each analysis form binds it to its own state. */
function CheckboxList({ label: text, options, selected, onToggle }: {
  label: string
  options: { name: string }[]
  selected: string[]
  onToggle: (name: string) => void
}) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '.04em' }}>
        {text}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 6 }}>
        {options.map(column => (
          <label key={column.name} style={{ fontSize: 13, display: 'flex', gap: 5, alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={selected.includes(column.name)}
              onChange={() => onToggle(column.name)}
            />
            {column.name}
          </label>
        ))}
      </div>
    </div>
  )
}

/** A labelled column picker: the analysis forms differ only in which columns they take. */
function ColumnSelect({ label: text, value, onChange, columns, allowEmpty = false }: {
  label: string
  value: string
  onChange: (value: string) => void
  columns: { name: string }[]
  allowEmpty?: boolean
}) {
  return (
    <div style={{ width: 180 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '.04em' }}>
        {text}
      </div>
      <select
        value={value}
        onChange={event => onChange(event.target.value)}
        style={{ padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border, #d1d5db)', fontSize: 13, width: '100%' }}
      >
        <option value="">{allowEmpty ? 'None' : 'Choose…'}</option>
        {columns.map(column => (
          <option key={column.name} value={column.name}>
            {column.name}
          </option>
        ))}
      </select>
    </div>
  )
}

function Pill({ children, tone = ACCENT }: { children: React.ReactNode; tone?: string }) {
  return (
    <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 999, fontSize: 12, fontWeight: 600, background: `${tone}1a`, color: tone }}>
      {children}
    </span>
  )
}

function Notice({ tone, children }: { tone: 'warn' | 'bad' | 'info'; children: React.ReactNode }) {
  const colors = { warn: '#b45309', bad: '#b91c1c', info: '#0369a1' }
  const backgrounds = { warn: '#fffbeb', bad: '#fef2f2', info: '#f0f9ff' }
  return (
    <div style={{ background: backgrounds[tone], color: colors[tone], border: `1px solid ${colors[tone]}33`, borderRadius: 8, padding: '8px 12px', fontSize: 13, marginBottom: 10 }}>
      {children}
    </div>
  )
}

/** The rendered analysis table: Table 1 and the comparison share one shape. */
function RenderedTable({ table }: { table: CohortRenderedTable }) {
  const columns = useMemo(() => {
    if (table.columns.length && typeof table.columns[0] === 'string') {
      return (table.columns as string[]).map((name, index) => ({ key: String(index), label: name }))
    }
    return table.columns as { key: string; label: string }[]
  }, [table.columns])
  const structured = table.rows.some(row => row.cells !== undefined)

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {structured ? (
              <>
                {columns.map(column => (
                  <th key={column.key} style={th} title={column.key}>
                    {column.label}
                  </th>
                ))}
              </>
            ) : (
              columns.map(column => <th key={column.key} style={th}>{column.label}</th>)
            )}
          </tr>
        </thead>
        <tbody>
          {structured
            ? table.rows.map((row, index) => (
                <tr key={`${row.label}-${index}`} style={row.header ? { background: '#fafafa' } : undefined}>
                  {columns.map(column => {
                    const text = row.cells?.[column.key] ?? ''
                    if (column.key === 'p') {
                      const adjusted = row.p_adjusted
                      return (
                        <td key={column.key} style={td} title={row.test || ''}>
                          {text}
                          {adjusted !== null && adjusted !== undefined && row.p !== null && row.p !== undefined && adjusted !== row.p ? (
                            <span style={{ ...muted, marginLeft: 4 }}>(raw {pText(row.p)})</span>
                          ) : null}
                        </td>
                      )
                    }
                    return (
                      <td key={column.key} style={{ ...td, fontWeight: row.header ? 600 : 400 }}>
                        {text}
                      </td>
                    )
                  })}
                </tr>
              ))
            : table.rows.map((row, index) => (
                <tr key={`${row.label}-${index}`}>
                  <td style={{ ...td, fontWeight: 600 }}>{row.label}</td>
                  <td style={td}>{row.value ?? ''}</td>
                  <td style={td}>{row.missing ?? ''}</td>
                </tr>
              ))}
        </tbody>
      </table>
      {table.rows.some(row => row.effect) && (
        <div style={{ ...muted, marginTop: 8 }}>
          Effect sizes:{' '}
          {table.rows
            .filter(row => row.effect)
            .map(row => (
              <span key={row.label} style={{ marginRight: 12 }}>
                {row.label}: {row.effect!.name} {row.effect!.estimate.toFixed(2)}
                {row.effect!.ci ? ` [${row.effect!.ci[0].toFixed(2)}, ${row.effect!.ci[1].toFixed(2)}]` : ''}{' '}
                ({row.effect!.magnitude || 'n/a'})
              </span>
            ))}
        </div>
      )}
      {table.notes && table.notes.length > 0 && (
        <ul style={{ ...muted, marginTop: 10, paddingLeft: 18 }}>
          {table.notes.map(note => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function FlowView({ flow }: { flow: CohortFlow }) {
  const exitsAfter = (id: string) => flow.exits.filter(exit => exit.after === id)
  return (
    <div>
      {flow.inconsistencies.length > 0 && (
        <Notice tone="bad">
          The flow does not add up: {flow.inconsistencies.join('; ')}. The trace is missing a step
          that changed the rows.
        </Notice>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {flow.main.map(box => (
          <div key={box.id}>
            <div
              style={{
                border: `1px solid ${ACCENT}55`,
                background: `${ACCENT}0d`,
                borderRadius: 8,
                padding: '10px 14px',
                display: 'flex',
                justifyContent: 'space-between',
                gap: 12,
              }}
            >
              <span style={{ fontSize: 13 }}>{box.label}</span>
              <strong style={{ fontSize: 14 }}>{box.n.toLocaleString()}</strong>
            </div>
            {exitsAfter(box.id).map(exit => (
              <div
                key={exit.id}
                style={{ marginLeft: 24, padding: '6px 12px', fontSize: 13, color: '#b91c1c', display: 'flex', justifyContent: 'space-between' }}
                title={(exit.details || []).join(' · ')}
              >
                <span>↳ {exit.label}</span>
                <span>−{exit.n.toLocaleString()}</span>
              </div>
            ))}
          </div>
        ))}
        {flow.analyses.map(box => (
          <div key={box.id} style={{ marginLeft: 24, padding: '8px 12px', borderLeft: `2px solid ${ACCENT}`, fontSize: 13, display: 'flex', justifyContent: 'space-between' }}>
            <span>{box.label}</span>
            <span>{box.n.toLocaleString()}</span>
          </div>
        ))}
      </div>
      {flow.notes.length > 0 && (
        <ul style={{ ...muted, marginTop: 12, paddingLeft: 18 }}>
          {flow.notes.map(note => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function QualityView({ report }: { report: CohortQuality }) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 14 }}>
        <span style={{ fontSize: 30, fontWeight: 700, color: bandColor(report.band) }}>{percent(report.score)}</span>
        <Pill tone={bandColor(report.band)}>{report.band}</Pill>
        <span style={muted}>
          {report.rows.toLocaleString()} rows × {report.columns} columns
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 10, marginBottom: 16 }}>
        {report.dimensions.map(dimension => (
          <div key={dimension.key} style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 10 }}>
            <div style={{ fontSize: 12, ...muted }}>{dimension.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: bandColor(dimension.band) }}>{percent(dimension.score)}</div>
            <div style={{ height: 4, background: '#f3f4f6', borderRadius: 2, marginTop: 6 }}>
              <div style={{ height: 4, width: percent(dimension.score), background: bandColor(dimension.band), borderRadius: 2 }} />
            </div>
          </div>
        ))}
      </div>
      {report.warnings.map(warning => (
        <Notice key={warning} tone="warn">{warning}</Notice>
      ))}
      {report.missing.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={label}>Missing values</div>
          <div style={muted}>
            {report.missing.slice(0, 8).map(item => `${item.column}: ${item.missing} (${percent(item.share)})`).join(' · ')}
          </div>
        </div>
      )}
      {report.outliers.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={label}>Values outside the IQR fences</div>
          <div style={muted}>
            {report.outliers.slice(0, 8).map(item => `${item.column}: ${item.rows} row(s)`).join(' · ')}
          </div>
        </div>
      )}
      {report.clinical_rules.length > 0 && (
        <div>
          <div style={label}>Study rules</div>
          <div style={muted}>
            {report.clinical_rules.map(rule => `${rule.name}: ${rule.rows} row(s) flagged`).join(' · ')}
          </div>
        </div>
      )}
    </div>
  )
}

function TraceView({ trace, onReplay, replaying, replay }: {
  trace: CohortTrace
  onReplay: () => void
  replaying: boolean
  replay?: { reconciled: boolean; problems: string[]; steps: { seq: number; kind: string; status: string; detail: string }[] }
}) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          {trace.chain.verified ? (
            <Pill tone="#059669">chain verified · {trace.chain.steps} step(s)</Pill>
          ) : (
            <Pill tone="#b91c1c">chain broken</Pill>
          )}
        </div>
        <button style={button()} onClick={onReplay} disabled={replaying}>
          {replaying ? 'Replaying…' : 'Replay the trace'}
        </button>
      </div>
      {!trace.chain.verified && (
        <Notice tone="bad">
          {trace.chain.problems.map(problem => (
            <div key={problem}>{problem}</div>
          ))}
        </Notice>
      )}
      {replay && (
        <Notice tone={replay.reconciled ? 'info' : 'bad'}>
          {replay.reconciled
            ? 'Replay reproduced every step: the analysed table is the one the trace describes.'
            : `Replay did not reproduce the table: ${replay.problems.join('; ')}`}
        </Notice>
      )}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={th}>#</th>
            <th style={th}>Step</th>
            <th style={th}>Details</th>
            <th style={th}>Hash</th>
          </tr>
        </thead>
        <tbody>
          {trace.steps.map(step => (
            <tr key={step.id}>
              <td style={td}>{step.seq}</td>
              <td style={td}>{step.kind}</td>
              <td style={td}>
                {step.kind === 'import'
                  ? String((step.params as { filename?: string }).filename ?? '')
                  : step.kind === 'derive'
                    ? `${String((step.params as { name?: string }).name ?? '')} = ${String((step.params as { expression?: string }).expression ?? '')}`
                    : step.kind === 'population'
                      ? String((step.params as { name?: string }).name ?? '')
                      : String((step.params as { action?: string }).action ?? '')}
                {typeof step.data.rows_in === 'number' && typeof step.data.rows_out === 'number' && (
                  <span style={{ ...muted, marginLeft: 6 }}>
                    {String(step.data.rows_in)} → {String(step.data.rows_out)} rows
                  </span>
                )}
              </td>
              <td style={{ ...td, fontFamily: 'monospace', fontSize: 11, color: '#9ca3af' }} title={step.hash}>
                {step.hash.slice(0, 10)}…
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {trace.steps.length === 0 && <div style={{ ...muted, marginTop: 8 }}>Nothing has been recorded yet. Upload a file to start the trace.</div>}
    </div>
  )
}

function PopulationPanel({ population, flow }: { population: CohortPopulation; flow?: CohortFlow }) {
  return (
    <div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'baseline', flexWrap: 'wrap', marginBottom: 12 }}>
        <strong>{population.name}</strong>
        <Pill>
          {population.n_included.toLocaleString()} of {population.n_base.toLocaleString()} rows
        </Pill>
        {population.superseded_by && <Pill tone="#d97706">superseded</Pill>}
        <span style={{ ...muted, fontFamily: 'monospace' }} title="fingerprint of the analysed rows">
          {population.fingerprint}
        </span>
      </div>
      {population.counts.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 14 }}>
          <thead>
            <tr>
              <th style={th}>Criterion</th>
              <th style={th}>Family</th>
              <th style={th}>Fires (all rows)</th>
              <th style={th}>First reason for</th>
            </tr>
          </thead>
          <tbody>
            {population.counts.map(count => (
              <tr key={count.id}>
                <td style={td}>{count.name}</td>
                <td style={{ ...td, ...muted }}>{count.kind}</td>
                <td style={td}>{count.marginal_base.toLocaleString()}</td>
                <td style={td}>{count.sequential.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {flow && <FlowView flow={flow} />}
    </div>
  )
}

export function CohortPage() {
  const { id: projectId } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const [tableId, setTableId] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('data')
  const [newName, setNewName] = useState('')
  const [newOrigin, setNewOrigin] = useState<'public' | 'synthetic'>('public')
  const [ticked, setTicked] = useState<string[]>([])
  const [populationName, setPopulationName] = useState('Adults with complete records')
  const [method, setMethod] = useState<CohortMethod>('table1')
  const [variables, setVariables] = useState<string[]>([])
  const [group, setGroup] = useState<string>('')
  const [outcome, setOutcome] = useState<string>('')
  const [adjust, setAdjust] = useState('holm')
  const [timeColumn, setTimeColumn] = useState<string>('')
  const [eventColumn, setEventColumn] = useState<string>('')
  const [covariates, setCovariates] = useState<string[]>([])
  const [testColumn, setTestColumn] = useState<string>('')
  const [cutoff, setCutoff] = useState<string>('')
  const [exposure, setExposure] = useState<string>('')
  const [stratum, setStratum] = useState<string>('')
  const [raters, setRaters] = useState<string[]>([])
  const [measure, setMeasure] = useState<'icc' | 'bland_altman' | 'kappa'>('icc')
  const [iccModel, setIccModel] = useState('ICC(2,1)')
  const [miTarget, setMiTarget] = useState<'compare' | 'logistic' | 'cox'>('compare')
  const [miCount, setMiCount] = useState('20')
  const [miIterations, setMiIterations] = useState('10')
  const [miSeed, setMiSeed] = useState('')
  /** Which analyses go into the dossier; empty means the server picks the current ones. */
  const [dossierIds, setDossierIds] = useState<string[]>([])
  const [analysis, setAnalysis] = useState<CohortAnalysis | null>(null)
  const [experimentId, setExperimentId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.getProject(projectId!),
    enabled: Boolean(projectId),
  })

  const { data: tables = [] } = useQuery({
    queryKey: ['cohort-tables', projectId],
    queryFn: () => cohortApi.listTables(projectId!),
    enabled: Boolean(projectId),
  })

  useEffect(() => {
    if (!tableId && tables.length > 0) setTableId(tables[0].id)
  }, [tables, tableId])

  const { data: table } = useQuery({
    queryKey: ['cohort-table', projectId, tableId],
    queryFn: () => cohortApi.getTable(projectId!, tableId!),
    enabled: Boolean(projectId) && Boolean(tableId),
  })

  const { data: criteria = [] } = useQuery({
    queryKey: ['cohort-criteria', projectId, tableId],
    queryFn: () => cohortApi.listCriteria(projectId!, tableId!),
    enabled: Boolean(projectId) && Boolean(tableId),
  })

  const { data: experiments = [] } = useQuery({
    queryKey: ['experiments', projectId],
    queryFn: () => api.listExperiments(projectId!),
    enabled: Boolean(projectId),
  })

  const activePopulation: (CohortPopulation & { version_no?: number }) | null = (() => {
    const population = table?.active_population
    if (!population) return null
    const version = table?.versions.find(item => item.id === population.version_id)
    return { ...population, version_no: version?.version_no }
  })()

  const { data: flow } = useQuery({
    queryKey: ['cohort-flow', projectId, tableId, activePopulation?.id],
    queryFn: () => cohortApi.flow(projectId!, tableId!, activePopulation!.id),
    enabled: Boolean(projectId) && Boolean(tableId) && Boolean(activePopulation),
  })

  const latest = table?.latest_version ?? null

  // A population names the version it was declared on. When a newer version exists the
  // analyses still run on the old one, so say so instead of letting the numbers look stale.
  const populationVersion = activePopulation
    ? table?.versions.find(version => version.id === activePopulation.version_id)
    : undefined
  const versionMoved =
    populationVersion && latest && latest.version_no > populationVersion.version_no
      ? latest
      : undefined

  const { data: qualityReport } = useQuery({
    queryKey: ['cohort-quality', projectId, tableId, latest?.id],
    queryFn: () => cohortApi.quality(projectId!, tableId!, latest!.id),
    enabled: Boolean(projectId) && Boolean(tableId) && Boolean(latest),
  })

  const { data: trace } = useQuery({
    queryKey: ['cohort-trace', projectId, tableId],
    queryFn: () => cohortApi.trace(projectId!, tableId!),
    enabled: Boolean(projectId) && Boolean(tableId) && tab === 'provenance',
  })

  const { data: analyses = [] } = useQuery({
    queryKey: ['cohort-analyses', projectId, tableId, activePopulation?.id],
    queryFn: () => cohortApi.listAnalyses(projectId!, tableId!, activePopulation!.id),
    enabled: Boolean(projectId) && Boolean(tableId) && Boolean(activePopulation),
  })

  const run = (fn: () => Promise<unknown>, after?: () => void) =>
    fn()
      .then(() => {
        setError(null)
        after?.()
      })
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : String(caught)))

  const createTable = useMutation({
    mutationFn: () => cohortApi.createTable(projectId!, { name: newName.trim(), data_origin: newOrigin }),
    onSuccess: created => {
      setNewName('')
      setTableId(created.id)
      qc.invalidateQueries({ queryKey: ['cohort-tables', projectId] })
    },
    onError: (caught: unknown) => setError(caught instanceof Error ? caught.message : String(caught)),
  })

  const upload = useMutation({
    mutationFn: (file: File) => cohortApi.uploadVersion(projectId!, tableId!, file),
    onSuccess: () => {
      setError(null)
      qc.invalidateQueries({ queryKey: ['cohort-table', projectId, tableId] })
      qc.invalidateQueries({ queryKey: ['cohort-tables', projectId] })
    },
    onError: (caught: unknown) => setError(caught instanceof Error ? caught.message : String(caught)),
  })

  const declarePopulation = useMutation({
    mutationFn: () => cohortApi.createPopulation(projectId!, tableId!, populationName.trim(), ticked),
    onSuccess: () => {
      setError(null)
      qc.invalidateQueries({ queryKey: ['cohort-table', projectId, tableId] })
    },
    onError: (caught: unknown) => setError(caught instanceof Error ? caught.message : String(caught)),
  })

  const replay = useMutation({
    mutationFn: () => cohortApi.replay(projectId!, tableId!),
    onError: (caught: unknown) => setError(caught instanceof Error ? caught.message : String(caught)),
  })

  const publish = useMutation({
    mutationFn: (analysisId: string) =>
      cohortApi.publish(projectId!, tableId!, analysisId, experimentId, []),
    onSuccess: async (_result, analysisId) => {
      setError(null)
      setNotice('Published. The numbers are now recorded metrics of the experiment.')
      const fresh = await cohortApi.getAnalysis(projectId!, tableId!, analysisId)
      setAnalysis(fresh)
    },
    onError: (caught: unknown) => setError(caught instanceof Error ? caught.message : String(caught)),
  })

  const columns = latest?.columns_meta ?? []
  const numericColumns = columns.filter(column => column.kind === 'numeric')
  const categoricalColumns = columns.filter(column => column.kind === 'categorical')

  const submitAnalysis = () => {
    if (!activePopulation) return
    const body: CohortAnalysisRequest = { method }
    if (method === 'table1' || method === 'descriptive') {
      body.variables = variables
      body.group = group || null
      body.adjust = adjust
    } else if (method === 'compare') {
      body.outcome = outcome
      body.group = group
      body.adjust = adjust
    } else if (method === 'survival') {
      body.time = timeColumn
      body.event = eventColumn
      body.group = group || null
    } else if (method === 'cox') {
      body.time = timeColumn
      body.event = eventColumn
      body.covariates = covariates
    } else if (method === 'diagnostic') {
      body.test = testColumn
      body.outcome = outcome
      body.cutoff = cutoff.trim() === '' ? null : Number(cutoff)
    } else if (method === 'ratio2x2') {
      body.exposure = exposure
      body.outcome = outcome
    } else if (method === 'logistic') {
      body.outcome = outcome
      body.covariates = covariates
    } else if (method === 'mantel_haenszel') {
      body.exposure = exposure
      body.outcome = outcome
      body.stratum = stratum
    } else if (method === 'agreement') {
      body.raters = raters
      body.measure = measure
      body.icc_model = iccModel
    } else if (method === 'mcar') {
      body.variables = variables
    } else if (method === 'multiple_imputation') {
      body.target = miTarget
      body.m = Number(miCount) || 20
      body.maxit = Number(miIterations) || 10
      body.seed = miSeed.trim() === '' ? null : Number(miSeed)
      if (miTarget === 'compare') {
        body.outcome = outcome
        body.group = group
      } else if (miTarget === 'logistic') {
        body.outcome = outcome
        body.covariates = covariates
      } else {
        body.time = timeColumn
        body.event = eventColumn
        body.covariates = covariates
      }
    }
    run(
      () => cohortApi.runAnalysis(projectId!, tableId!, activePopulation.id, body),
      () => {
        qc.invalidateQueries({ queryKey: ['cohort-analyses', projectId, tableId, activePopulation.id] })
        qc.invalidateQueries({ queryKey: ['cohort-flow', projectId, tableId, activePopulation.id] })
      },
    )
      .then(() => cohortApi.listAnalyses(projectId!, tableId!, activePopulation.id))
      .then(list => setAnalysis(list.find(item => item.status === 'current') ?? list[0] ?? null))
      .catch(() => undefined)
  }

  const toggle = (list: string[], value: string) =>
    list.includes(value) ? list.filter(item => item !== value) : [...list, value]

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <ProjectHeader projectId={projectId!} name={project?.name} />
      <p style={{ ...muted, marginTop: 0 }}>
        A versioned cohort table with a declared analysis population. Every number states the rows and the
        data version it was computed on; a result computed on a superseded population is marked stale.
      </p>

      {error && <Notice tone="bad">{error}</Notice>}
      {notice && <Notice tone="info">{notice}</Notice>}

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 16 }}>
        <select
          value={tableId ?? ''}
          onChange={event => {
            setTableId(event.target.value || null)
            setAnalysis(null)
            setTicked([])
          }}
          style={{ ...input, width: 260 }}
        >
          <option value="">Select a cohort table…</option>
          {tables.map(item => (
            <option key={item.id} value={item.id}>
              {item.name} ({item.latest_version ? `${item.latest_version.rows} rows` : 'no data'})
            </option>
          ))}
        </select>
        <input placeholder="New table name" value={newName} onChange={event => setNewName(event.target.value)} style={{ ...input, width: 220 }} />
        <select value={newOrigin} onChange={event => setNewOrigin(event.target.value as 'public' | 'synthetic')} style={{ ...input, width: 150 }}>
          <option value="public">Public data</option>
          <option value="synthetic">Synthetic data</option>
        </select>
        <button style={button(true)} disabled={!newName.trim() || createTable.isPending} onClick={() => createTable.mutate()}>
          Create table
        </button>
      </div>

      {!table && <div style={{ ...card, ...muted }}>Create a cohort table, then upload a CSV, Excel or Parquet file.</div>}

      {table && (
        <>
          <nav style={{ display: 'flex', gap: 4, borderBottom: '1px solid #e5e7eb', marginBottom: 16 }}>
            {TABS.map(item => (
              <button
                key={item.key}
                onClick={() => setTab(item.key)}
                style={{
                  padding: '8px 14px',
                  border: 'none',
                  borderBottom: tab === item.key ? `2px solid ${ACCENT}` : '2px solid transparent',
                  background: 'transparent',
                  fontWeight: tab === item.key ? 700 : 500,
                  color: tab === item.key ? ACCENT : '#6b7280',
                  cursor: 'pointer',
                  fontSize: 13,
                }}
              >
                {item.label}
              </button>
            ))}
          </nav>

          {tab === 'data' && (
            <div style={card}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div>
                  <div style={label}>Data</div>
                  <div style={{ ...muted, marginTop: 4 }}>
                    {table.data_origin} cohort · {table.versions.length} version(s)
                    {latest ? ` · latest v${latest.version_no}: ${latest.rows.toLocaleString()} rows × ${latest.columns} columns` : ''}
                  </div>
                </div>
                <label style={{ ...button(true), display: 'inline-block' }}>
                  {upload.isPending ? 'Uploading…' : 'Upload a file'}
                  <input
                    type="file"
                    accept=".csv,.tsv,.txt,.xlsx,.xlsm,.parquet"
                    style={{ display: 'none' }}
                    onChange={event => {
                      const file = event.target.files?.[0]
                      if (file) upload.mutate(file)
                      event.target.value = ''
                    }}
                  />
                </label>
              </div>
              {latest?.parse_report && (
                <div style={{ ...muted, background: '#f9fafb', borderRadius: 8, padding: 10, marginBottom: 12 }}>
                  Read {latest.parse_report.filename} as {latest.parse_report.encoding ?? 'binary'}
                  {latest.parse_report.delimiter ? `, delimiter "${latest.parse_report.delimiter}"` : ''}:{' '}
                  {latest.parse_report.rows} rows.
                  {latest.parse_report.skipped_lines > 0 && ` ${latest.parse_report.skipped_lines} line(s) skipped.`}
                  {latest.parse_report.blanks > 0 && ` ${latest.parse_report.blanks} blank row(s) dropped.`}
                  {latest.parse_report.warnings.map(warning => (
                    <div key={warning} style={{ color: '#b45309' }}>{warning}</div>
                  ))}
                </div>
              )}
              {columns.length > 0 && (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr>
                        <th style={th}>Column</th>
                        <th style={th}>Type</th>
                        <th style={th}>Missing</th>
                        <th style={th}>Levels</th>
                      </tr>
                    </thead>
                    <tbody>
                      {columns.map(column => (
                        <tr key={column.name}>
                          <td style={td}>{column.name}</td>
                          <td style={{ ...td, ...muted }}>{column.kind}</td>
                          <td style={td}>{column.missing}</td>
                          <td style={td}>{column.levels ?? '–'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {tab === 'population' && (
            <div style={card}>
              <div style={{ ...label, marginBottom: 8 }}>Declare the analysis population</div>
              {criteria.length === 0 ? (
                <Notice tone="info">
                  This table has no study configuration yet, so there is nothing to tick. Add a
                  <code style={{ margin: '0 4px' }}>mask_families</code> block to the table configuration
                  (for example a plausibility range on a numeric column) and the criteria appear here.
                </Notice>
              ) : (
                <div style={{ marginBottom: 12 }}>
                  {criteria.map(criterion => (
                    <label key={criterion.id} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '6px 0', fontSize: 13 }}>
                      <input
                        type="checkbox"
                        checked={ticked.includes(criterion.id)}
                        onChange={() => setTicked(current => toggle(current, criterion.id))}
                        style={{ marginTop: 3 }}
                      />
                      <span>
                        <strong>{criterion.name}</strong>{' '}
                        <span style={{ ...muted }}>({criterion.kind}{criterion.columns.length ? ` · ${criterion.columns.join(', ')}` : ''})</span>
                        {criterion.description && <div style={muted}>{criterion.description}</div>}
                      </span>
                    </label>
                  ))}
                </div>
              )}
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 16 }}>
                <input value={populationName} onChange={event => setPopulationName(event.target.value)} style={{ ...input, width: 320 }} />
                <button style={button(true)} onClick={() => declarePopulation.mutate()} disabled={!populationName.trim() || declarePopulation.isPending}>
                  Declare population
                </button>
              </div>
              {activePopulation && versionMoved && (
                <Notice tone="warn">
                  The active population is declared on v{activePopulation.version_no}; v
                  {versionMoved.version_no} is newer. Analyses keep using v
                  {activePopulation.version_no} — declare a population on the newer version to
                  analyse what it contains.
                </Notice>
              )}
              {activePopulation ? (
                <PopulationPanel population={activePopulation} flow={flow} />
              ) : (
                <div style={muted}>No population yet. Upload a file first.</div>
              )}
            </div>
          )}

          {tab === 'analysis' && (
            <div style={card}>
              {!activePopulation ? (
                <div style={muted}>Declare an analysis population first.</div>
              ) : (
                <>
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: 12 }}>
                    <div style={{ width: 170 }}>
                      <div style={label}>Method</div>
                      <select
                        value={method}
                        onChange={event => {
                          setMethod(event.target.value as CohortMethod)
                          setAnalysis(null)
                        }}
                        style={input}
                      >
                        <option value="table1">Table 1</option>
                        <option value="descriptive">Describe</option>
                        <option value="compare">Compare means</option>
                        <option value="survival">Survival (KM + log-rank)</option>
                        <option value="cox">Cox regression</option>
                        <option value="diagnostic">Diagnostic accuracy</option>
                        <option value="ratio2x2">2×2 association</option>
                        <option value="logistic">Logistic regression</option>
                        <option value="mantel_haenszel">Mantel-Haenszel</option>
                        <option value="agreement">Agreement (ICC / Bland-Altman / kappa)</option>
                        <option value="mcar">Missingness (Little's MCAR)</option>
                        <option value="multiple_imputation">Multiple imputation (pooled)</option>
                      </select>
                    </div>

                    {(method === 'survival' || method === 'cox') && (
                      <>
                        <ColumnSelect label="Follow-up time" value={timeColumn} onChange={setTimeColumn} columns={columns} />
                        <ColumnSelect label="Event (1 = event)" value={eventColumn} onChange={setEventColumn} columns={columns} />
                      </>
                    )}

                    {method === 'survival' && (
                      <ColumnSelect
                        label="Group (optional)"
                        value={group}
                        onChange={setGroup}
                        columns={categoricalColumns}
                        allowEmpty
                      />
                    )}

                    {method === 'compare' && (
                      <>
                        <ColumnSelect label="Outcome" value={outcome} onChange={setOutcome} columns={numericColumns} />
                        <ColumnSelect label="Group" value={group} onChange={setGroup} columns={categoricalColumns} />
                      </>
                    )}

                    {method === 'diagnostic' && (
                      <>
                        <ColumnSelect label="Test value" value={testColumn} onChange={setTestColumn} columns={numericColumns} />
                        <ColumnSelect label="Outcome (2 levels)" value={outcome} onChange={setOutcome} columns={categoricalColumns} />
                        <div style={{ width: 140 }}>
                          <div style={label}>Cut-off (optional)</div>
                          <input
                            value={cutoff}
                            onChange={event => setCutoff(event.target.value)}
                            placeholder="Youden's J"
                            inputMode="decimal"
                            style={input}
                          />
                        </div>
                      </>
                    )}

                    {method === 'ratio2x2' && (
                      <>
                        <ColumnSelect label="Exposure (2 levels)" value={exposure} onChange={setExposure} columns={categoricalColumns} />
                        <ColumnSelect label="Outcome (2 levels)" value={outcome} onChange={setOutcome} columns={categoricalColumns} />
                      </>
                    )}

                    {method === 'logistic' && (
                      <ColumnSelect label="Outcome (2 levels)" value={outcome} onChange={setOutcome} columns={categoricalColumns} />
                    )}

                    {method === 'mantel_haenszel' && (
                      <>
                        <ColumnSelect label="Exposure (2 levels)" value={exposure} onChange={setExposure} columns={categoricalColumns} />
                        <ColumnSelect label="Outcome (2 levels)" value={outcome} onChange={setOutcome} columns={categoricalColumns} />
                        <ColumnSelect label="Stratify by" value={stratum} onChange={setStratum} columns={columns} />
                      </>
                    )}

                    {method === 'multiple_imputation' && (
                      <>
                        <div style={{ width: 200 }}>
                          <div style={label}>Pool this analysis</div>
                          <select
                            value={miTarget}
                            onChange={event => setMiTarget(event.target.value as 'compare' | 'logistic' | 'cox')}
                            style={input}
                          >
                            <option value="compare">Mean difference (2 groups)</option>
                            <option value="logistic">Logistic regression</option>
                            <option value="cox">Cox regression</option>
                          </select>
                        </div>
                        <div style={{ width: 110 }}>
                          <div style={label}>Imputations</div>
                          <input value={miCount} onChange={event => setMiCount(event.target.value)} inputMode="numeric" style={input} />
                        </div>
                        <div style={{ width: 110 }}>
                          <div style={label}>Iterations</div>
                          <input value={miIterations} onChange={event => setMiIterations(event.target.value)} inputMode="numeric" style={input} />
                        </div>
                        <div style={{ width: 120 }}>
                          <div style={label}>Seed (optional)</div>
                          <input value={miSeed} onChange={event => setMiSeed(event.target.value)} inputMode="numeric" style={input} />
                        </div>
                      </>
                    )}

                    {method === 'multiple_imputation' && miTarget === 'compare' && (
                      <>
                        <ColumnSelect label="Outcome" value={outcome} onChange={setOutcome} columns={numericColumns} />
                        <ColumnSelect label="Group (2 levels)" value={group} onChange={setGroup} columns={categoricalColumns} />
                      </>
                    )}

                    {method === 'multiple_imputation' && miTarget !== 'compare' && (
                      <ColumnSelect
                        label="Outcome"
                        value={outcome}
                        onChange={setOutcome}
                        columns={miTarget === 'logistic' ? categoricalColumns : numericColumns}
                      />
                    )}

                    {method === 'multiple_imputation' && miTarget === 'cox' && (
                      <>
                        <ColumnSelect label="Follow-up time" value={timeColumn} onChange={setTimeColumn} columns={columns} />
                        <ColumnSelect label="Event (1 = event)" value={eventColumn} onChange={setEventColumn} columns={columns} />
                      </>
                    )}

                    {method === 'agreement' && (
                      <>
                        <div style={{ width: 170 }}>
                          <div style={label}>Measure</div>
                          <select
                            value={measure}
                            onChange={event => setMeasure(event.target.value as 'icc' | 'bland_altman' | 'kappa')}
                            style={input}
                          >
                            <option value="icc">ICC</option>
                            <option value="bland_altman">Bland-Altman</option>
                            <option value="kappa">Cohen's kappa</option>
                          </select>
                        </div>
                        {measure === 'icc' && (
                          <div style={{ width: 190 }}>
                            <div style={label}>ICC model</div>
                            <select value={iccModel} onChange={event => setIccModel(event.target.value)} style={input}>
                              <option value="ICC(2,1)">ICC(2,1) absolute agreement</option>
                              <option value="ICC(3,1)">ICC(3,1) consistency</option>
                            </select>
                          </div>
                        )}
                      </>
                    )}

                    {(method === 'table1' || method === 'descriptive' || method === 'compare') && (
                      <>
                        {(method === 'table1' || method === 'descriptive') && (
                          <ColumnSelect
                            label="Group (optional)"
                            value={group}
                            onChange={setGroup}
                            columns={categoricalColumns}
                            allowEmpty
                          />
                        )}
                        <div style={{ width: 170 }}>
                          <div style={label}>Multiplicity</div>
                          <select value={adjust} onChange={event => setAdjust(event.target.value)} style={input} disabled={!group}>
                            <option value="holm">Holm</option>
                            <option value="fdr_bh">Benjamini-Hochberg</option>
                            <option value="bonferroni">Bonferroni</option>
                            <option value="none">None</option>
                          </select>
                        </div>
                      </>
                    )}

                    <button style={button(true)} onClick={submitAnalysis}>
                      Run
                    </button>
                  </div>

                  {method === 'diagnostic' && (
                    <div style={{ ...muted, marginBottom: 12 }}>
                      With no cut-off the sample's Youden-optimal one is used and reported as such — it
                      is optimistic and needs out-of-sample validation.
                    </div>
                  )}

                  {(method === 'table1' || method === 'descriptive' || method === 'mcar') && (
                    <CheckboxList
                      label={method === 'mcar' ? 'Variables to test (numeric)' : 'Variables'}
                      options={method === 'mcar' ? numericColumns : columns}
                      selected={variables}
                      onToggle={name => setVariables(current => toggle(current, name))}
                    />
                  )}

                  {(method === 'cox' ||
                    method === 'logistic' ||
                    (method === 'multiple_imputation' && miTarget !== 'compare')) && (
                    <CheckboxList
                      label="Covariates"
                      options={columns.filter(
                        column =>
                          column.name !== timeColumn &&
                          column.name !== eventColumn &&
                          column.name !== outcome,
                      )}
                      selected={covariates}
                      onToggle={name => setCovariates(current => toggle(current, name))}
                    />
                  )}

                  {method === 'mcar' && (
                    <div style={{ marginBottom: 12, fontSize: 13, color: '#6b7280' }}>
                      Little's test says whether the missing data are consistent with MCAR. Failing to
                      reject it does not prove MCAR — it only means the data do not contradict it.
                    </div>
                  )}

                  {method === 'agreement' && (
                    <CheckboxList
                      label={
                        measure === 'kappa'
                          ? 'Raters (exactly two, categorical)'
                          : 'Measurements (two or more, numeric)'
                      }
                      options={measure === 'kappa' ? columns : numericColumns}
                      selected={raters}
                      onToggle={name => setRaters(current => toggle(current, name))}
                    />
                  )}

                  {analysis && analysis.status === 'stale' && (
                    <Notice tone="warn">
                      This result is stale: {analysis.stale_reason}. Recompute it before publishing its numbers.
                    </Notice>
                  )}

                  {analysis?.table && (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <div style={muted}>
                          {analysis.method} · n = {analysis.n.toLocaleString()} · population{' '}
                          <code>{analysis.population_fingerprint}</code> · {analysis.engine_version}
                        </div>
                        <button
                          style={button()}
                          onClick={() =>
                            cohortApi
                              .exportAnalysis(projectId!, tableId!, analysis.id, `cohort-${analysis.method}.csv`)
                              .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : String(caught)))
                          }
                        >
                          Export CSV
                        </button>
                      </div>
                      <RenderedTable table={analysis.table} />

                      {analysis.values.length > 0 && (
                        <div style={{ marginTop: 16, borderTop: '1px solid #e5e7eb', paddingTop: 12 }}>
                          <div style={{ ...label, marginBottom: 6 }}>Publish numbers into an experiment</div>
                          <div style={{ ...muted, marginBottom: 8 }}>
                            A published number becomes a recorded metric, so a manuscript draft can cite it
                            and the number checker accepts it. A stale result cannot be published.
                          </div>
                          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                            <select value={experimentId} onChange={event => setExperimentId(event.target.value)} style={{ ...input, width: 260 }}>
                              <option value="">Choose an experiment…</option>
                              {experiments.map(item => (
                                <option key={item.id} value={item.id}>{item.name}</option>
                              ))}
                            </select>
                            <button
                              style={button(true)}
                              disabled={!experimentId || analysis.status !== 'current' || publish.isPending}
                              onClick={() => {
                                setNotice(null)
                                publish.mutate(analysis.id)
                              }}
                            >
                              {publish.isPending ? 'Publishing…' : `Publish ${analysis.values.length} value(s)`}
                            </button>
                          </div>
                        </div>
                      )}
                    </>
                  )}

                  {analyses.length > 0 && (
                    <div style={{ marginTop: 16 }}>
                      <div style={{ ...label, marginBottom: 6 }}>Earlier analyses in this population</div>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr>
                            <th style={th}>Method</th>
                            <th style={th}>n</th>
                            <th style={th}>Status</th>
                            <th style={th}>When</th>
                          </tr>
                        </thead>
                        <tbody>
                          {analyses.map(item => (
                            <tr key={item.id} style={{ cursor: 'pointer' }} onClick={() => setAnalysis(item)}>
                              <td style={td}>{item.method}</td>
                              <td style={td}>{item.n.toLocaleString()}</td>
                              <td style={td}>
                                <Pill tone={item.status === 'current' ? '#059669' : item.status === 'stale' ? '#d97706' : '#b91c1c'}>
                                  {item.status}
                                </Pill>
                              </td>
                              <td style={{ ...td, ...muted }}>{new Date(item.created_at).toLocaleString()}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {tab === 'report' && (
            <div style={card}>
              <div style={{ ...label, marginBottom: 6 }}>Study dossier</div>
              <div style={{ ...muted, marginBottom: 12 }}>
                One Word document with the provenance (data version, content hash, analysis
                population and its fingerprint), the participant flow, the data handling, the
                missing-data treatment and the results you choose — each result stamped with the
                population it was computed on.
              </div>
              <Notice tone="info">
                The dossier is not a compliance certificate and not a signed record: it does not
                certify conformance with STROBE or any other guideline. It records what was
                computed, on which rows.
              </Notice>
              {analyses.length === 0 ? (
                <div style={{ ...muted, marginBottom: 12 }}>
                  No analysis in this population yet. Run one, then include it here.
                </div>
              ) : (
                <div style={{ marginBottom: 14 }}>
                  <div style={{ ...label, marginBottom: 6 }}>Results to include</div>
                  {analyses.map(item => {
                    const checked = dossierIds.length === 0 ? item.status === 'current' : dossierIds.includes(item.id)
                    return (
                      <label
                        key={item.id}
                        style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13, padding: '4px 0' }}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => {
                            const base = dossierIds.length === 0
                              ? analyses.filter(a => a.status === 'current').map(a => a.id)
                              : dossierIds
                            setDossierIds(base.includes(item.id)
                              ? base.filter(id => id !== item.id)
                              : [...base, item.id])
                          }}
                        />
                        <span>{item.method}</span>
                        <span style={muted}>n = {item.n.toLocaleString()}</span>
                        {item.status !== 'current' && <Pill tone="#d97706">{item.status}</Pill>}
                      </label>
                    )
                  })}
                  <div style={{ ...muted, marginTop: 6 }}>
                    A stale result is left out unless you tick it; when you do, the document marks it
                    as stale.
                  </div>
                </div>
              )}
              <button
                style={button(true)}
                onClick={() => {
                  setNotice(null)
                  const chosen = dossierIds.length > 0
                    ? dossierIds
                    : analyses.filter(item => item.status === 'current').map(item => item.id)
                  cohortApi
                    .dossier(projectId!, tableId!, chosen, `study-dossier-${table.name}.docx`)
                    .then(() => setNotice('The dossier was downloaded.'))
                    .catch((caught: unknown) =>
                      setError(caught instanceof Error ? caught.message : String(caught)),
                    )
                }}
              >
                Download the study dossier (.docx)
              </button>
            </div>
          )}

          {tab === 'quality' && (
            <div style={card}>
              {qualityReport ? <QualityView report={qualityReport} /> : <div style={muted}>Upload a file to score its quality.</div>}
            </div>
          )}

          {tab === 'provenance' && (
            <div style={card}>
              {trace ? (
                <TraceView trace={trace} onReplay={() => replay.mutate()} replaying={replay.isPending} replay={replay.data} />
              ) : (
                <div style={muted}>Loading the trace…</div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
