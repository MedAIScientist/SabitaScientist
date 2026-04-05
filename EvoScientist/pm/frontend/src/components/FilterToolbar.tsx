import React from 'react'
import { Task, Member } from '../api'
import { SortKey, PrioritySet } from '../hooks/useTaskFilters'

interface FilterToolbarProps {
  search: string
  onSearchChange: (v: string) => void
  priorities: PrioritySet
  onTogglePriority: (p: Task['priority']) => void
  sort: SortKey
  onSortChange: (v: SortKey) => void
  assigneeId: string | null
  onAssigneeChange: (v: string | null) => void
  members: Member[]
}

const inputStyle: React.CSSProperties = {
  background: 'var(--surface-input)',
  border: '1px solid var(--border)',
  color: 'var(--text)',
  borderRadius: 4,
  padding: '4px 8px',
  fontFamily: 'var(--font-mono)',
  fontSize: 13,
  outline: 'none',
}

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  cursor: 'pointer',
}

const labelStyle: React.CSSProperties = {
  fontSize: 11,
  color: 'var(--text-3)',
  fontFamily: 'var(--font-mono)',
  marginRight: 4,
  whiteSpace: 'nowrap',
}

type ChipAccent = { high: string; medium: string; low: string }

const CHIP_ACCENTS: ChipAccent = {
  high: '#f43f5e',
  medium: '#f59e0b',
  low: '#22c55e',
}

const CHIP_LABELS: Record<Task['priority'], string> = {
  high: 'CRIT',
  medium: 'NORM',
  low: 'ROUT',
}

const PRIORITIES: Task['priority'][] = ['high', 'medium', 'low']

function chipStyle(priority: Task['priority'], active: boolean): React.CSSProperties {
  const accent = CHIP_ACCENTS[priority]
  return {
    background: active ? `rgba(${hexToRgb(accent)},0.15)` : 'transparent',
    border: active ? `1px solid ${accent}` : '1px solid var(--border)',
    color: active ? accent : 'var(--text-3)',
    borderRadius: 3,
    padding: '2px 8px',
    fontSize: 11,
    fontWeight: 700,
    cursor: 'pointer',
    fontFamily: 'var(--font-mono)',
  }
}

function hexToRgb(hex: string): string {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  if (!result) return '255,255,255'
  return `${parseInt(result[1], 16)},${parseInt(result[2], 16)},${parseInt(result[3], 16)}`
}

export function FilterToolbar({
  search,
  onSearchChange,
  priorities,
  onTogglePriority,
  sort,
  onSortChange,
  assigneeId,
  onAssigneeChange,
  members,
}: FilterToolbarProps) {
  const containerStyle: React.CSSProperties = {
    display: 'flex',
    gap: 8,
    alignItems: 'center',
    padding: '6px 0',
    flexWrap: 'wrap',
  }

  return (
    <div style={containerStyle}>
      <input
        type="text"
        placeholder="🔬 Search experiments…"
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
        style={inputStyle}
      />

      {PRIORITIES.map((priority) => (
        <button
          key={priority}
          onClick={() => onTogglePriority(priority)}
          style={chipStyle(priority, priorities.has(priority))}
        >
          {CHIP_LABELS[priority]}
        </button>
      ))}

      <select
        value={sort}
        onChange={(e) => onSortChange(e.target.value as SortKey)}
        style={selectStyle}
      >
        <option value="created">Created</option>
        <option value="deadline">Deadline</option>
        <option value="priority">Priority</option>
      </select>

      <span style={labelStyle}>Researcher:</span>
      <select
        value={assigneeId ?? ''}
        onChange={(e) => {
          const value = e.target.value
          onAssigneeChange(value === '' ? null : value)
        }}
        style={selectStyle}
      >
        <option value="">All</option>
        {members.map((m) => (
          <option key={m.user_id} value={m.user_id}>
            {m.username}
          </option>
        ))}
      </select>
    </div>
  )
}
