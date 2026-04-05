import { useState } from 'react'

interface Props {
  type: 'note' | 'result'
  onSave: (data: { title: string; body: string }) => void
  onCancel: () => void
  initialTitle?: string
  initialBody?: string
}

export function EntryEditor({ type, onSave, onCancel, initialTitle = '', initialBody = '' }: Props) {
  const [title, setTitle] = useState(initialTitle)
  const [body, setBody] = useState(initialBody)

  const label = type === 'note' ? 'NOTE' : 'RESULT'
  const accent = type === 'note' ? '#22d3ee' : '#10b981'

  return (
    <div style={{
      background: '#0a1220',
      border: `1px solid ${accent}33`,
      borderRadius: 6,
      padding: '12px 14px',
    }}>
      <div style={{ fontSize: 8, color: accent, fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', marginBottom: 8 }}>
        {initialTitle ? `EDIT ${label}` : `NEW ${label}`}
      </div>

      <input
        value={title}
        onChange={e => setTitle(e.target.value)}
        placeholder="Title…"
        style={{
          width: '100%', boxSizing: 'border-box',
          background: '#070b12', border: '1px solid rgba(100,140,200,0.18)',
          borderRadius: 4, color: '#e2e8f0', fontSize: 11, padding: '6px 8px',
          fontFamily: 'inherit', marginBottom: 6, outline: 'none',
        }}
      />

      <textarea
        value={body}
        onChange={e => setBody(e.target.value)}
        rows={5}
        placeholder="Markdown content…"
        style={{
          width: '100%', boxSizing: 'border-box',
          background: '#070b12', border: '1px solid rgba(100,140,200,0.18)',
          borderRadius: 4, color: '#94a3b8', fontSize: 10, padding: '6px 8px',
          fontFamily: 'var(--font-mono)', resize: 'vertical', outline: 'none',
          marginBottom: 8,
        }}
      />

      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
        <button
          onClick={onCancel}
          style={{
            background: 'rgba(100,140,200,0.06)', border: '1px solid rgba(100,140,200,0.14)',
            borderRadius: 3, padding: '4px 10px', color: '#64748b',
            fontSize: 9, fontFamily: 'var(--font-mono)', cursor: 'pointer',
          }}
        >
          CANCEL
        </button>
        <button
          onClick={() => onSave({ title: title.trim(), body })}
          disabled={!title.trim()}
          style={{
            background: `${accent}18`, border: `1px solid ${accent}40`,
            borderRadius: 3, padding: '4px 10px', color: accent,
            fontSize: 9, fontFamily: 'var(--font-mono)', cursor: 'pointer',
            opacity: !title.trim() ? 0.4 : 1,
          }}
        >
          SAVE
        </button>
      </div>
    </div>
  )
}
