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
  const accent = type === 'note' ? '#ff8015' : '#10b981'

  return (
    <div style={{
      background: 'var(--surface-2)',
      border: `1px solid var(--border)`,
      borderRadius: 6,
      padding: '12px 14px',
    }}>
      <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ color: 'var(--text-dim)' }}>{initialTitle ? 'EDIT' : 'NEW'}</span>
        <span style={{ color: accent, background: `${accent}18`, border: `1px solid ${accent}33`, borderRadius: 2, padding: '1px 5px' }}>{label}</span>
      </div>

      <input
        value={title}
        onChange={e => setTitle(e.target.value)}
        placeholder="Title…"
        style={{
          width: '100%', boxSizing: 'border-box',
          background: 'var(--surface-input)', border: '1px solid var(--border)',
          borderRadius: 4, color: 'var(--text)', fontSize: 20, padding: '6px 8px',
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
          background: 'var(--surface-input)', border: '1px solid var(--border)',
          borderRadius: 4, color: 'var(--text-2)', fontSize: 16, padding: '6px 8px',
          fontFamily: 'var(--font-mono)', resize: 'vertical', outline: 'none',
          marginBottom: 8,
        }}
      />

      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
        <button
          onClick={onCancel}
          style={{
            background: 'var(--surface-input)', border: '1px solid var(--border)',
            borderRadius: 3, padding: '4px 10px', color: 'var(--text-3)',
            fontSize: 15, fontFamily: 'var(--font-mono)', cursor: 'pointer',
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
            fontSize: 15, fontFamily: 'var(--font-mono)', cursor: 'pointer',
            opacity: !title.trim() ? 0.4 : 1,
          }}
        >
          SAVE
        </button>
      </div>
    </div>
  )
}
