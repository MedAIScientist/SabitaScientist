import React, { useEffect, useState } from 'react'
import { api } from '../../api'

/**
 * Search-and-pick a platform user by username.
 *
 * `valueLabel` lets a caller show the name of an already-saved selection (the id
 * alone is a uuid, which reads as noise).
 */
export function UserPicker({
  value,
  valueLabel,
  onChange,
  placeholder = 'search users…',
}: {
  value: string | null
  valueLabel?: string | null
  onChange: (userId: string | null) => void
  placeholder?: string
}) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<{ id: string; username: string }[]>([])
  const [picked, setPicked] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const term = q.trim()
    if (!term) {
      setResults([])
      return
    }
    let alive = true
    // Debounced so typing does not fire a request per keystroke.
    const timer = setTimeout(() => {
      api
        .searchUsers(term)
        .then(r => {
          if (alive) setResults(r)
        })
        .catch(() => {
          if (alive) setResults([])
        })
    }, 200)
    return () => {
      alive = false
      clearTimeout(timer)
    }
  }, [q])

  const shown = picked ?? valueLabel ?? (value ? `${value.slice(0, 8)}…` : null)

  return (
    <div style={{ position: 'relative' }}>
      {shown ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            flex: 1, padding: '8px 11px', background: 'var(--surface-input)',
            border: '1px solid var(--border)', borderRadius: 7,
            color: 'var(--text)', fontSize: 16,
          }}>{shown}</span>
          <button
            type="button"
            onClick={() => { onChange(null); setPicked(null); setQ('') }}
            style={{
              cursor: 'pointer', padding: '8px 12px', borderRadius: 7,
              background: 'transparent', border: '1px solid var(--border)',
              color: 'var(--text-muted)', fontSize: 15, fontFamily: 'var(--font-mono)',
            }}
          >Clear</button>
        </div>
      ) : (
        <input
          value={q}
          placeholder={placeholder}
          onChange={e => { setQ(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          style={{
            width: '100%', padding: '9px 11px', background: 'var(--surface-input)',
            border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)',
            fontSize: 16, outline: 'none',
          }}
        />
      )}
      {open && !shown && results.length > 0 && (
        <div style={{
          position: 'absolute', zIndex: 20, top: '100%', left: 0, right: 0,
          marginTop: 4, background: 'var(--surface-card)',
          border: '1px solid var(--border)', borderRadius: 7,
          maxHeight: 200, overflowY: 'auto',
          boxShadow: '0 8px 24px rgba(0,0,0,0.35)',
        }}>
          {results.map(u => (
            <div
              key={u.id}
              onMouseDown={() => {
                onChange(u.id)
                setPicked(u.username)
                setQ('')
                setOpen(false)
              }}
              style={{
                padding: '8px 11px', cursor: 'pointer', fontSize: 16,
                color: 'var(--text)', borderBottom: '1px solid var(--border-subtle)',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--surface-card-hover)' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
            >{u.username}</div>
          ))}
        </div>
      )}
    </div>
  )
}
