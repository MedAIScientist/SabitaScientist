// EvoScientist/pm/frontend/src/components/task/LabNotesTab.tsx
import React from 'react'

interface Comment {
  id: string
  body: string
  created_at: string
}

interface Props {
  comments: Comment[]
  commentBody: string
  setCommentBody: (v: string) => void
  onSubmit: () => void
  isPending: boolean
}

export function LabNotesTab({ comments, commentBody, setCommentBody, onSubmit, isPending }: Props) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{
          fontSize: 15, fontWeight: 700, color: 'var(--text-dim)',
          letterSpacing: '0.12em', textTransform: 'uppercase',
          fontFamily: 'var(--font-mono)',
        }}>Lab Notes</span>
        <div style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
        <span style={{
          fontSize: 15, color: 'var(--text-dim)',
          background: 'var(--border-subtle)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 9, padding: '1px 7px',
          fontFamily: 'var(--font-mono)',
        }}>{comments.length}</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        {comments.map((c) => (
          <div key={c.id} style={{
            background: 'var(--surface-comment)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 7, padding: '10px 12px',
          }}>
            <p style={{ margin: '0 0 5px', fontSize: 22, color: 'var(--text)', lineHeight: 1.55 }}>{c.body}</p>
            <p style={{ margin: 0, fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
              {c.created_at.slice(0, 10)}
            </p>
          </div>
        ))}
        {comments.length === 0 && (
          <p style={{ color: 'var(--text-muted)', fontSize: 21, fontStyle: 'italic', padding: '4px 0' }}>
            No lab notes yet.
          </p>
        )}
      </div>

      <form
        aria-label="add-lab-note"
        onSubmit={(e) => { e.preventDefault(); onSubmit() }}
        style={{ display: 'flex', gap: 8, marginTop: 'auto' }}
      >
        <input
          value={commentBody}
          onChange={e => setCommentBody(e.target.value)}
          placeholder="Add a lab note…"
          required
          style={{
            flex: 1, padding: '9px 12px',
            background: 'var(--surface-input)',
            border: '1px solid var(--border)',
            borderRadius: 7, color: 'var(--text)',
            fontSize: 21, outline: 'none',
            transition: 'border-color 0.14s',
          }}
          onFocus={e => { e.currentTarget.style.borderColor = 'rgba(255,128,21,0.3)' }}
          onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
        />
        <button
          type="submit"
          disabled={isPending}
          style={{
            padding: '9px 16px', fontSize: 20, cursor: 'pointer',
            background: 'rgba(255,128,21,0.1)',
            border: '1px solid rgba(255,128,21,0.25)',
            borderRadius: 7, color: '#ff8015', fontWeight: 700,
            letterSpacing: '0.05em', transition: 'background 0.14s',
            fontFamily: 'var(--font-mono)',
          }}
        >POST</button>
      </form>
    </div>
  )
}
