import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

export function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(username, password)
      navigate('/projects')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100vh', background: 'var(--bg)',
    }}>
      {/* Subtle grid pattern */}
      <div style={{
        position: 'fixed', inset: 0, pointerEvents: 'none',
        backgroundImage:
          'linear-gradient(rgba(255,128,21,0.025) 1px, transparent 1px),' +
          'linear-gradient(90deg, rgba(255,128,21,0.025) 1px, transparent 1px)',
        backgroundSize: '44px 44px',
      }} />

      <form
        onSubmit={handleSubmit}
        style={{
          position: 'relative',
          background: 'var(--surface-panel)',
          border: '1px solid var(--border)',
          borderRadius: 12, padding: '32px 32px 28px',
          width: 330, display: 'flex', flexDirection: 'column', gap: 16,
          boxShadow: '0 24px 64px rgba(0,0,0,0.55)',
          animation: 'fadeInUp 0.3s ease',
        }}
      >
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
          <img
            src="/sabita.jpg"
            alt="SABITA"
            style={{ height: 38, borderRadius: 6, display: 'block' }}
          />
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 15, color: 'var(--text-dim)', letterSpacing: '0.1em', lineHeight: 1.5 }}>
            RESEARCH · PM
          </div>
        </div>

        <div style={{ height: 1, background: 'var(--border-subtle)' }} />

        {error && (
          <div style={{
            padding: '8px 12px',
            background: 'rgba(244,63,94,0.08)',
            border: '1px solid rgba(244,63,94,0.2)',
            borderRadius: 6, color: '#f43f5e',
            fontSize: 20, fontFamily: 'var(--font-mono)',
          }}>{error}</div>
        )}

        {(['USERNAME', 'PASSWORD'] as const).map((label, i) => (
          <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            <label style={{
              fontSize: 15, fontWeight: 700, color: 'var(--text-dim)',
              letterSpacing: '0.12em', fontFamily: 'var(--font-mono)',
            }}>{label}</label>
            <input
              type={i === 1 ? 'password' : 'text'}
              placeholder={i === 1 ? '••••••••' : 'username'}
              value={i === 0 ? username : password}
              onChange={e => i === 0 ? setUsername(e.target.value) : setPassword(e.target.value)}
              required
              style={{
                padding: '9px 11px',
                background: 'var(--surface-input)',
                border: '1px solid var(--border)',
                borderRadius: 7, color: 'var(--text)',
                fontSize: 22, outline: 'none',
                transition: 'border-color 0.14s',
              }}
              onFocus={e => { e.currentTarget.style.borderColor = 'rgba(255,128,21,0.32)' }}
              onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
            />
          </div>
        ))}

        <button
          type="submit"
          disabled={loading}
          style={{
            marginTop: 4, padding: '10px', fontSize: 16,
            cursor: loading ? 'default' : 'pointer',
            background: loading ? 'rgba(255,128,21,0.07)' : 'rgba(255,128,21,0.12)',
            border: '1px solid rgba(255,128,21,0.28)',
            borderRadius: 7, color: '#ff8015',
            fontWeight: 700, letterSpacing: '0.1em',
            transition: 'background 0.14s',
            fontFamily: 'var(--font-mono)',
          }}
          onMouseEnter={e => { if (!loading) e.currentTarget.style.background = 'rgba(255,128,21,0.22)' }}
          onMouseLeave={e => { e.currentTarget.style.background = loading ? 'rgba(255,128,21,0.07)' : 'rgba(255,128,21,0.12)' }}
        >
          {loading ? 'AUTHENTICATING…' : 'SIGN IN'}
        </button>
      </form>
    </div>
  )
}
