import React, { useState } from 'react'

interface StatusOption {
  value: string
  label: string
}

interface Phase {
  id: string
  name: string
}

interface Props {
  count: number
  label?: string
  phases: Phase[]
  statusOptions: StatusOption[]
  onStatusChange: (status: string) => void
  onPhaseChange: (phaseId: string | null) => void
  onClear: () => void
}

const selectStyle: React.CSSProperties = {
  padding: '5px 10px',
  background: 'var(--surface-input)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  color: 'var(--text)',
  fontSize: 16,
  cursor: 'pointer',
  fontFamily: 'var(--font-mono)',
  outline: 'none',
}

export function BulkActionBar({ count, label, phases, statusOptions, onStatusChange, onPhaseChange, onClear }: Props) {
  const [statusVal, setStatusVal] = useState('')
  const [phaseVal, setPhaseVal] = useState('')
  const [clearHovered, setClearHovered] = useState(false)

  return (
    <div style={{
      position: 'fixed',
      bottom: 24,
      left: '50%',
      transform: 'translateX(-50%)',
      zIndex: 200,
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      background: 'var(--surface)',
      border: '1px solid rgba(var(--accent-rgb),0.35)',
      borderRadius: 10,
      padding: '10px 16px',
      boxShadow: '0 8px 32px rgba(0,0,0,0.35), 0 0 0 1px rgba(var(--accent-rgb),0.12)',
      backdropFilter: 'blur(12px)',
    }}>
      <span style={{
        fontSize: 14,
        fontWeight: 600,
        color: 'var(--accent)',
        whiteSpace: 'nowrap',
      }}>
        {/* label is a plural noun ("tasks"): "1 task selected", "3 tasks selected" */}
        {count} {label ? `${count === 1 ? label.replace(/s$/, '') : label} ` : ''}selected
      </span>

      <div style={{ width: 1, height: 20, background: 'var(--border)', flexShrink: 0 }} />

      <select
        data-testid="bulk-status-select"
        value={statusVal}
        onChange={e => {
          onStatusChange(e.target.value)
          setStatusVal('')
        }}
        style={selectStyle}
      >
        <option value="" disabled>Set status…</option>
        {statusOptions.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      <select
        data-testid="bulk-phase-select"
        value={phaseVal}
        onChange={e => {
          const val = e.target.value
          onPhaseChange(val === '__none__' ? null : val)
          setPhaseVal('')
        }}
        style={selectStyle}
      >
        <option value="" disabled>Set phase…</option>
        <option value="__none__">No phase</option>
        {phases.map(p => (
          <option key={p.id} value={p.id}>{p.name}</option>
        ))}
      </select>

      <button
        onClick={onClear}
        onMouseEnter={() => setClearHovered(true)}
        onMouseLeave={() => setClearHovered(false)}
        style={{
          padding: '5px 10px',
          background: 'none',
          border: '1px solid var(--border)',
          borderRadius: 6,
          fontSize: 16,
          cursor: 'pointer',
          fontFamily: 'var(--font-mono)',
          transition: 'border-color 0.14s, color 0.14s',
          borderColor: clearHovered ? 'rgba(244,63,94,0.4)' : 'var(--border)',
          color: clearHovered ? '#f43f5e' : 'var(--text-dim)',
        }}
      >✕ Clear</button>
    </div>
  )
}
