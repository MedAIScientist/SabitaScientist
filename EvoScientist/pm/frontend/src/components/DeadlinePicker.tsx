import { useState } from 'react'

interface Props {
  value: string          // 'YYYY-MM-DD' or ''
  onChange: (v: string) => void
  inputStyle?: React.CSSProperties
}

function toLocalISO(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const PRESETS = [
  {
    label: 'Tomorrow',
    key: 'tomorrow',
    get: () => { const d = new Date(); d.setDate(d.getDate() + 1); return toLocalISO(d) },
  },
  {
    label: 'Next week',
    key: 'week',
    get: () => { const d = new Date(); d.setDate(d.getDate() + 7); return toLocalISO(d) },
  },
  {
    label: 'Next month',
    key: 'month',
    get: () => { const d = new Date(); d.setMonth(d.getMonth() + 1); return toLocalISO(d) },
  },
]

export function DeadlinePicker({ value, onChange, inputStyle }: Props) {
  const [hovered, setHovered] = useState<string | null>(null)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {/* Preset chips */}
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
        {PRESETS.map(p => {
          const preset = p.get()
          const active = value === preset
          const isHovered = hovered === p.key
          return (
            <button
              key={p.key}
              type="button"
              onMouseEnter={() => setHovered(p.key)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => onChange(active ? '' : preset)}
              style={{
                padding: '3px 9px',
                fontSize: 9,
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
                letterSpacing: '0.06em',
                borderRadius: 4,
                cursor: 'pointer',
                border: active
                  ? '1px solid rgba(34,211,238,0.5)'
                  : '1px solid var(--border)',
                background: active
                  ? 'rgba(34,211,238,0.12)'
                  : isHovered
                  ? 'rgba(34,211,238,0.06)'
                  : 'var(--surface-input)',
                color: active ? '#22d3ee' : 'var(--text-2)',
                transition: 'background 0.12s, border-color 0.12s, color 0.12s',
              }}
            >
              {p.label}
            </button>
          )
        })}
        {value && (
          <button
            type="button"
            onMouseEnter={() => setHovered('clear')}
            onMouseLeave={() => setHovered(null)}
            onClick={() => onChange('')}
            style={{
              padding: '3px 9px',
              fontSize: 9,
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              letterSpacing: '0.06em',
              borderRadius: 4,
              cursor: 'pointer',
              border: '1px solid rgba(244,63,94,0.25)',
              background: hovered === 'clear' ? 'rgba(244,63,94,0.1)' : 'transparent',
              color: '#f43f5e',
              transition: 'background 0.12s',
            }}
          >
            ✕ Clear
          </button>
        )}
      </div>

      {/* Custom date input */}
      <input
        type="date"
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{
          ...inputStyle,
          fontSize: 11,
          colorScheme: 'dark',
        }}
        onFocus={e => { e.currentTarget.style.borderColor = 'rgba(34,211,238,0.3)' }}
        onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
      />
    </div>
  )
}
