import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Assist, Experiment } from '../api'
import { useAssistStream } from '../hooks/useAssistStream'

const TARGET_OPTIONS = [
  { value: 'hypothesis', label: 'Hypothesis' },
  { value: 'protocol',   label: 'Protocol' },
  { value: 'entry_body', label: 'New Note body' },
  { value: 'result_body', label: 'New Result body' },
] as const

type TargetOption = typeof TARGET_OPTIONS[number]['value']

interface Props {
  experiment: Experiment
  projectId: string
  onClose: () => void
  onApplyHypothesis: (text: string) => void
  onApplyProtocol: (text: string) => void
  onApplyEntryBody: (text: string, type: 'note' | 'result') => void
}

export function AiAssistPanel({
  experiment, projectId, onClose,
  onApplyHypothesis, onApplyProtocol, onApplyEntryBody,
}: Props) {
  const qc = useQueryClient()
  const [prompt, setPrompt] = useState('')
  const [target, setTarget] = useState<TargetOption>('hypothesis')
  const [agentType, setAgentType] = useState<string>('writing')
  const [activeAssistId, setActiveAssistId] = useState<string | null>(null)
  const [appliedText, setAppliedText] = useState<string | null>(null)

  const { output, isStreaming, streamStatus } = useAssistStream(activeAssistId)

  const isRunning = isStreaming || streamStatus === 'streaming'
  const isDone = streamStatus === 'done'
  const hasFailed = streamStatus === 'failed'

  const createMutation = useMutation({
    mutationFn: () => api.createAssist(projectId, experiment.id, {
      prompt,
      agent_type: agentType,
      target_field: target === 'result_body' ? 'entry_body' : target,
    }),
    onSuccess: (assist: Assist) => {
      setActiveAssistId(assist.id)
      setAppliedText(null)
      qc.invalidateQueries({ queryKey: ['assists', experiment.id] })
    },
  })

  const cancelMutation = useMutation({
    mutationFn: () => api.cancelAssist(activeAssistId!),
    onSuccess: () => setActiveAssistId(null),
  })

  function handleApply() {
    const text = output || ''
    if (!text) return
    if (target === 'hypothesis') onApplyHypothesis(text)
    else if (target === 'protocol') onApplyProtocol(text)
    else if (target === 'entry_body') onApplyEntryBody(text, 'note')
    else if (target === 'result_body') onApplyEntryBody(text, 'result')
    setAppliedText(text)
    setActiveAssistId(null)
  }

  function handleDiscard() {
    setActiveAssistId(null)
    setAppliedText(null)
  }

  const accent = '#a78bfa'  // purple — distinct from orange (tasks) and green (results)

  return (
    <div style={{
      position: 'fixed', right: 420, top: 0, bottom: 0, width: 360,
      background: 'var(--surface-panel)', borderLeft: '1px solid var(--border)',
      zIndex: 31, display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '12px 14px 10px', borderBottom: '1px solid var(--border-subtle)',
        flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <span style={{
          fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)',
          color: accent, letterSpacing: '0.08em',
        }}>
          ✦ AI ASSISTANT
        </span>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', color: 'var(--text-3)', fontSize: 22, cursor: 'pointer', padding: 2 }}
        >✕</button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '10px 14px' }}>
        {/* Target field selector */}
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontWeight: 700, marginBottom: 5 }}>
            APPLY TO
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
            {TARGET_OPTIONS.map(opt => (
              <button
                key={opt.value}
                onClick={() => setTarget(opt.value)}
                style={{
                  background: target === opt.value ? `${accent}14` : 'var(--surface-input)',
                  border: `1px solid ${target === opt.value ? `${accent}44` : 'var(--border)'}`,
                  borderRadius: 3, padding: '5px 8px',
                  color: target === opt.value ? accent : 'var(--text-3)',
                  fontSize: 15, fontFamily: 'var(--font-mono)', cursor: 'pointer',
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Agent type selector */}
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontWeight: 700, marginBottom: 5 }}>
            AI AGENT
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
            {[
              { value: 'writing', label: '✍ Writing', color: '#a78bfa' },
              { value: 'research', label: '🔬 Research', color: '#6366f1' },
              { value: 'code', label: '💻 Code', color: '#10b981' },
              { value: 'data_analysis', label: '📊 Analysis', color: '#f59e0b' },
            ].map(opt => (
              <button
                key={opt.value}
                onClick={() => setAgentType(opt.value)}
                style={{
                  background: agentType === opt.value ? `${opt.color}14` : 'var(--surface-input)',
                  border: `1px solid ${agentType === opt.value ? `${opt.color}44` : 'var(--border)'}`,
                  borderRadius: 3, padding: '5px 8px',
                  color: agentType === opt.value ? opt.color : 'var(--text-3)',
                  fontSize: 15, fontFamily: 'var(--font-mono)', cursor: 'pointer',
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Prompt */}
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontWeight: 700, marginBottom: 5 }}>
            PROMPT
          </div>
          <textarea
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            rows={4}
            disabled={isRunning}
            placeholder="Describe what to write…"
            style={{
              width: '100%', boxSizing: 'border-box',
              background: 'var(--surface-input)', border: `1px solid ${accent}33`,
              borderRadius: 4, color: 'var(--text-2)', fontSize: 16,
              padding: '6px 8px', fontFamily: 'inherit', resize: 'vertical',
              outline: 'none', opacity: isRunning ? 0.5 : 1,
            }}
          />
        </div>

        {/* Generate / Stop button */}
        {isRunning ? (
          <button
            onClick={() => cancelMutation.mutate()}
            style={{
              width: '100%', background: 'rgba(244,63,94,0.08)',
              border: '1px solid rgba(244,63,94,0.28)', borderRadius: 3,
              padding: '6px 0', color: '#f43f5e', fontSize: 16, fontWeight: 700,
              fontFamily: 'var(--font-mono)', cursor: 'pointer', marginBottom: 10,
            }}
          >
            ■ STOP
          </button>
        ) : (
          <button
            onClick={() => createMutation.mutate()}
            disabled={!prompt.trim()}
            style={{
              width: '100%', background: `${accent}14`,
              border: `1px solid ${accent}44`, borderRadius: 3,
              padding: '6px 0', color: accent, fontSize: 16, fontWeight: 700,
              fontFamily: 'var(--font-mono)', cursor: 'pointer', marginBottom: 10,
              opacity: !prompt.trim() ? 0.4 : 1,
            }}
          >
            ▶ GENERATE
          </button>
        )}

        {/* Output */}
        {(isRunning || isDone || hasFailed || output) && (
          <div style={{
            border: `1px solid ${accent}22`, borderRadius: 4, overflow: 'hidden', marginBottom: 8,
          }}>
            <div style={{
              background: `${accent}08`, padding: '4px 8px',
              fontSize: 15, color: accent, fontFamily: 'var(--font-mono)', fontWeight: 700,
            }}>
              {isRunning ? 'GENERATING…' : hasFailed ? 'FAILED' : 'OUTPUT'}
            </div>
            <div style={{
              padding: '6px 8px', background: 'var(--surface-input)',
              maxHeight: 200, overflowY: 'auto',
            }}>
              <pre style={{
                fontSize: 15, color: 'var(--text-2)', fontFamily: 'var(--font-mono)',
                margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.6,
              }}>
                {output || (isRunning ? '…' : '')}
                {isRunning && <span style={{ color: accent }}>▋</span>}
              </pre>
            </div>
            {isDone && output && (
              <div style={{ display: 'flex', gap: 4, padding: '6px 8px', borderTop: `1px solid ${accent}18` }}>
                <button
                  onClick={handleApply}
                  style={{
                    flex: 1, background: `${accent}14`, border: `1px solid ${accent}44`,
                    borderRadius: 3, padding: '4px 0', color: accent,
                    fontSize: 15, fontFamily: 'var(--font-mono)', cursor: 'pointer', fontWeight: 700,
                  }}
                >
                  ✔ APPLY
                </button>
                <button
                  onClick={handleDiscard}
                  style={{
                    flex: 1, background: 'var(--surface-input)', border: '1px solid var(--border)',
                    borderRadius: 3, padding: '4px 0', color: 'var(--text-3)',
                    fontSize: 15, fontFamily: 'var(--font-mono)', cursor: 'pointer',
                  }}
                >
                  ✕ DISCARD
                </button>
              </div>
            )}
          </div>
        )}

        {appliedText && (
          <div style={{
            fontSize: 15, color: '#10b981', fontFamily: 'var(--font-mono)',
            padding: '4px 0',
          }}>
            ✓ Applied to {TARGET_OPTIONS.find(o => o.value === target)?.label ?? target}
          </div>
        )}
      </div>
    </div>
  )
}
