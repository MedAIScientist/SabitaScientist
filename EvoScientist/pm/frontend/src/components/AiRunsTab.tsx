import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Run, Task } from '../api'
import { useRunStream } from '../hooks/useRunStream'

const AGENTS: { key: 'research' | 'code' | 'data_analysis' | 'writing'; label: string; icon: string; desc: string }[] = [
  { key: 'research',      label: 'Research',  icon: '🔬', desc: 'Find protocols & methods' },
  { key: 'code',          label: 'Code',      icon: '⚙',  desc: 'Implement scripts' },
  { key: 'data_analysis', label: 'Analysis',  icon: '📊', desc: 'Metrics & plots' },
  { key: 'writing',       label: 'Writing',   icon: '✍',  desc: 'Draft report' },
]

const STATUS_COLORS: Record<string, string> = {
  done: '#10b981', failed: '#f43f5e', cancelled: '#64748b',
  running: '#ff8015', pending: '#f59e0b',
}

const sectionLabel: React.CSSProperties = {
  fontSize: 16, color: 'var(--text-dim)', letterSpacing: '0.1em',
  fontWeight: 700, marginBottom: 5, fontFamily: 'var(--font-mono)',
}

interface Props { task: Task; projectId: string }

export function AiRunsTab({ task, projectId }: Props) {
  const qc = useQueryClient()
  const defaultPrompt = [task.title, task.description].filter(Boolean).join('. ')

  const [selectedAgent, setSelectedAgent] = useState<'research' | 'code' | 'data_analysis' | 'writing'>('research')
  const [prompt, setPrompt] = useState(defaultPrompt)
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null)

  const { output: streamOutput, isStreaming, streamStatus } = useRunStream(activeRunId)

  const { data: runs = [] } = useQuery({
    queryKey: ['runs', task.id],
    queryFn: () => api.listRuns(projectId, task.id),
  })

  const createRunMutation = useMutation({
    mutationFn: () => api.createRun(projectId, task.id, { agent_type: selectedAgent, prompt }),
    onSuccess: (run) => {
      setActiveRunId(run.id)
      qc.invalidateQueries({ queryKey: ['runs', task.id] })
    },
  })

  const cancelMutation = useMutation({
    mutationFn: (runId: string) => api.cancelRun(runId),
    onSuccess: () => {
      setActiveRunId(null)
      qc.invalidateQueries({ queryKey: ['runs', task.id] })
    },
  })

  if (activeRunId && !isStreaming && streamStatus !== 'idle' && streamStatus !== 'streaming') {
    setActiveRunId(null)
    qc.invalidateQueries({ queryKey: ['runs', task.id] })
  }

  const hasHistory = runs.length > 0
  const isRunning = isStreaming || createRunMutation.isPending

  const handleAddToNotes = (run: Run) => {
    if (!run.output) return
    const body = `**[${run.agent_type.toUpperCase()} Run · ${run.created_at.slice(0, 10)}]**\n\n${run.output}`
    api.addComment(projectId, task.id, body).then(() =>
      qc.invalidateQueries({ queryKey: ['comments', task.id] })
    )
  }

  return (
    <div style={{ padding: '10px 8px', background: 'var(--surface-2)', height: '100%', overflowY: 'auto' }}>

      {/* Agent picker */}
      <div style={sectionLabel}>SELECT AGENT</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, marginBottom: 10 }}>
        {AGENTS.map(a => (
          <button
            key={a.key}
            onClick={() => setSelectedAgent(a.key)}
            style={{
              background: selectedAgent === a.key ? 'rgba(255,128,21,0.08)' : 'var(--surface-card)',
              border: selectedAgent === a.key ? '1px solid rgba(255,128,21,0.28)' : '1px solid var(--border-subtle)',
              borderRadius: 3, padding: '5px 6px', textAlign: 'left', cursor: 'pointer',
            }}
          >
            <div style={{ fontSize: 20, color: selectedAgent === a.key ? '#ff8015' : 'var(--text-muted)', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
              {a.icon} {a.label}
            </div>
            <div style={{ fontSize: 16, color: 'var(--text-dim)', marginTop: 1 }}>{a.desc}</div>
          </button>
        ))}
      </div>

      {/* Prompt */}
      <div style={sectionLabel}>PROMPT</div>
      <textarea
        value={prompt}
        onChange={e => setPrompt(e.target.value)}
        rows={3}
        disabled={isRunning}
        placeholder="Describe what the agent should do…"
        style={{
          width: '100%', boxSizing: 'border-box',
          background: 'var(--surface-input)', border: '1px solid rgba(255,128,21,0.18)',
          borderRadius: 3, color: 'var(--text-2)', fontSize: 20, padding: '5px 6px', resize: 'none',
          fontFamily: 'var(--font-sans)', marginBottom: 6, opacity: isRunning ? 0.5 : 1,
          outline: 'none',
        }}
      />

      {/* Run button */}
      <button
        onClick={() => createRunMutation.mutate()}
        disabled={isRunning || !prompt.trim()}
        style={{
          width: '100%', background: 'rgba(255,128,21,0.1)', border: '1px solid rgba(255,128,21,0.28)',
          borderRadius: 3, padding: '6px 0', color: '#ff8015', fontSize: 20, fontWeight: 700,
          fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', cursor: 'pointer',
          marginBottom: 10, opacity: (isRunning || !prompt.trim()) ? 0.4 : 1,
        }}
      >
        {hasHistory ? '▶ RUN AGAIN' : '▶ RUN SABITA AI'}
      </button>

      {/* Active run (streaming) */}
      {activeRunId && (
        <div style={{ border: '1px solid rgba(255,128,21,0.2)', borderRadius: 4, overflow: 'hidden', marginBottom: 8 }}>
          <div style={{ background: 'rgba(255,128,21,0.06)', padding: '5px 8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 6, height: 6, background: '#ff8015', borderRadius: '50%' }} />
              <span style={{ fontSize: 18, color: '#ff8015', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                {selectedAgent.toUpperCase()} · RUNNING
              </span>
            </div>
            <button
              onClick={() => cancelMutation.mutate(activeRunId)}
              style={{ background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.2)', borderRadius: 2, padding: '1px 6px', color: '#f43f5e', fontSize: 18, cursor: 'pointer', fontFamily: 'var(--font-mono)' }}
            >■ STOP</button>
          </div>
          <div style={{ padding: '6px 8px', background: 'var(--surface-input)', minHeight: 60, maxHeight: 120, overflowY: 'auto' }}>
            <pre style={{ fontSize: 18, color: 'var(--text-2)', fontFamily: 'var(--font-mono)', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.6 }}>
              {streamOutput || '…'}
              {isStreaming && <span style={{ color: '#ff8015' }}>▋</span>}
            </pre>
          </div>
        </div>
      )}

      {/* Run history */}
      {runs.length === 0 && !activeRunId ? (
        <div style={{ fontSize: 18, color: 'var(--text-dim)', textAlign: 'center', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
          NO PREVIOUS RUNS
        </div>
      ) : (
        <>
          <div style={{ ...sectionLabel, marginTop: 4 }}>
            RUN HISTORY · {runs.length} {runs.length === 1 ? 'RUN' : 'RUNS'}
          </div>
          {runs.map(run => (
            <RunCard
              key={run.id}
              run={run}
              expanded={expandedRunId === run.id}
              onToggle={() => setExpandedRunId(expandedRunId === run.id ? null : run.id)}
              onAddToNotes={handleAddToNotes}
            />
          ))}
        </>
      )}
    </div>
  )
}

function RunCard({ run, expanded, onToggle, onAddToNotes }: {
  run: Run; expanded: boolean
  onToggle: () => void; onAddToNotes: (r: Run) => void
}) {
  const color = STATUS_COLORS[run.status] ?? '#64748b'
  const duration = run.started_at && run.finished_at
    ? `${Math.round((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000)}s`
    : null

  return (
    <div style={{ border: `1px solid ${color}22`, borderRadius: 4, overflow: 'hidden', marginBottom: 4 }}>
      <button
        onClick={onToggle}
        style={{ width: '100%', background: `${color}0a`, padding: '5px 8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', border: 'none', cursor: 'pointer' }}
      >
        <div>
          <span style={{ fontSize: 18, color, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
            {run.status === 'done' ? '✓' : run.status === 'failed' ? '✗' : '◌'} {run.agent_type.toUpperCase()}
          </span>
          <span style={{ fontSize: 16, color: 'var(--text-dim)', marginLeft: 6 }}>
            {run.created_at.slice(0, 10)}{duration ? ` · ${duration}` : ''}
          </span>
        </div>
        <span style={{ fontSize: 20, color: 'var(--text-3)' }}>{expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && (
        <div style={{ padding: '6px 8px', background: 'var(--surface-input)' }}>
          {run.output ? (
            <pre style={{ fontSize: 18, color: 'var(--text-2)', fontFamily: 'var(--font-mono)', margin: '0 0 6px', whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.5, maxHeight: 120, overflowY: 'auto' }}>
              {run.output}
            </pre>
          ) : run.error ? (
            <div style={{ fontSize: 18, color: '#f43f5e', marginBottom: 6 }}>{run.error}</div>
          ) : null}
          {run.output && (
            <div style={{ display: 'flex', gap: 4 }}>
              <button
                onClick={() => navigator.clipboard.writeText(run.output!)}
                style={{ background: 'rgba(255,128,21,0.06)', border: '1px solid rgba(255,128,21,0.15)', borderRadius: 2, padding: '2px 6px', fontSize: 16, color: '#ff8015', cursor: 'pointer', fontFamily: 'var(--font-mono)' }}
              >📋 Copy</button>
              <button
                onClick={() => onAddToNotes(run)}
                style={{ background: 'rgba(255,128,21,0.06)', border: '1px solid rgba(255,128,21,0.15)', borderRadius: 2, padding: '2px 6px', fontSize: 16, color: '#ff8015', cursor: 'pointer', fontFamily: 'var(--font-mono)' }}
              >💬 Add to Notes</button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
