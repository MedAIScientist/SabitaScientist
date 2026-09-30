// EvoScientist/pm/frontend/src/components/task/taskStyles.ts
import React from 'react'

export const STATUS_META: Record<string, { color: string; bg: string; label: string }> = {
  todo:        { color: '#ff8015', bg: 'rgba(255,128,21,0.08)',  label: 'Planned'     },
  in_progress: { color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', label: 'In progress' },
  done:        { color: '#10b981', bg: 'rgba(16,185,129,0.08)', label: 'Complete'    },
}

export const PRIORITY_META: Record<string, { color: string; bg: string; label: string }> = {
  high:   { color: '#f43f5e', bg: 'rgba(244,63,94,0.1)',   label: 'Critical' },
  medium: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  label: 'Standard' },
  low:    { color: '#22c55e', bg: 'rgba(34,197,94,0.1)',   label: 'Routine'  },
}

export function isOverdue(deadline: string | null | undefined): boolean {
  return Boolean(deadline) && new Date(deadline!) < new Date()
}

export const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 11px',
  background: 'var(--surface-input)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  color: 'var(--text)',
  fontSize: 17,
  outline: 'none',
  boxSizing: 'border-box',
  fontFamily: 'inherit',
}

export const selectStyle: React.CSSProperties = {
  ...inputStyle,
  cursor: 'pointer',
}

export const labelStyle: React.CSSProperties = {
  fontSize: 15,
  fontWeight: 700,
  color: 'var(--text-dim)',
  letterSpacing: '0.12em',
  textTransform: 'uppercase' as const,
  fontFamily: 'var(--font-mono)',
  marginBottom: 5,
  display: 'block',
}
