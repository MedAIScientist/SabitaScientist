import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { useTheme } from '../theme'

export function ProfilePage() {
  const { username, isAdmin, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()

  const isDark = theme === 'dark'

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordSaving, setPasswordSaving] = useState(false)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [passwordSaved, setPasswordSaved] = useState(false)

  async function handlePasswordSave() {
    setPasswordError(null)
    setPasswordSaved(false)
    if (newPassword.length < 6) {
      setPasswordError('Password must be at least 6 characters')
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('Passwords do not match')
      return
    }
    setPasswordSaving(true)
    try {
      await api.setPassword(newPassword)
      setNewPassword('')
      setConfirmPassword('')
      setPasswordSaved(true)
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : 'Could not update password')
    } finally {
      setPasswordSaving(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>

      {/* Header */}
      <div style={{
        padding: '0 28px', height: 54,
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'var(--surface-header)', backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <h1 className="page-title" style={{ fontSize: 18 }}>Profile</h1>
        </div>
      </div>

      {/* Content */}
      <div style={{ maxWidth: 480, margin: '48px auto', padding: '0 28px' }}>

        {/* Avatar + name */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 18, marginBottom: 36 }}>
          <div style={{
            width: 56, height: 56, borderRadius: '50%',
            background: 'linear-gradient(135deg, #ff8015, #8b5cf6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 28, fontWeight: 700, color: '#fff',
            fontFamily: 'var(--font-mono)',
            boxShadow: '0 0 20px rgba(var(--accent-rgb),0.25)',
          }}>
            {username?.[0]?.toUpperCase() ?? '?'}
          </div>
          <div>
            <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)' }}>
              {username}
            </div>
            <div style={{ fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2, letterSpacing: '0.04em' }}>
              Researcher
            </div>
          </div>
        </div>

        {/* Settings card */}
        <div style={{
          background: 'var(--surface-card)',
          border: '1px solid var(--border)',
          borderRadius: 10,
          overflow: 'hidden',
          marginBottom: 16,
        }}>
          {/* Theme row */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '16px 20px',
            borderBottom: '1px solid var(--border-subtle)',
          }}>
            <div>
              <div style={{ fontSize: 17, fontWeight: 500, color: 'var(--text-heading)', marginBottom: 2 }}>
                Appearance
              </div>
              <div style={{ fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                {isDark ? 'DARK MODE' : 'LIGHT MODE'}
              </div>
            </div>
            <button
              onClick={toggleTheme}
              title={`Switch to ${isDark ? 'light' : 'dark'} mode`}
              style={{
                width: 52, height: 28, borderRadius: 14,
                border: 'none', cursor: 'pointer',
                background: isDark ? 'rgba(var(--accent-rgb),0.15)' : 'rgba(var(--accent-rgb),0.25)',
                position: 'relative',
                transition: 'background 0.2s',
                flexShrink: 0,
                outline: '1px solid rgba(var(--accent-rgb),0.3)',
              }}
              aria-pressed={!isDark}
            >
              {/* Track label */}
              <span style={{
                position: 'absolute', top: '50%', transform: 'translateY(-50%)',
                fontSize: 15, fontFamily: 'var(--font-mono)', fontWeight: 700,
                letterSpacing: '0.04em',
                left: isDark ? 'auto' : 8,
                right: isDark ? 8 : 'auto',
                color: 'var(--accent)',
                opacity: 0.8,
              }}>
                {isDark ? '🌙' : '☀'}
              </span>
              {/* Thumb */}
              <span style={{
                position: 'absolute', top: 4,
                left: isDark ? 4 : 24,
                width: 20, height: 20, borderRadius: '50%',
                background: isDark ? 'var(--accent)' : '#f59e0b',
                boxShadow: isDark ? '0 0 8px rgba(var(--accent-rgb),0.5)' : '0 0 8px rgba(245,158,11,0.5)',
                transition: 'left 0.2s, background 0.2s, box-shadow 0.2s',
              }} />
            </button>
          </div>

          {/* Username row */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '16px 20px',
          }}>
            <div>
              <div style={{ fontSize: 17, fontWeight: 500, color: 'var(--text-heading)', marginBottom: 2 }}>
                Username
              </div>
              <div style={{ fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                {username}
              </div>
            </div>
            <span style={{
              fontSize: 15, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
              letterSpacing: '0.04em',
            }}>Read-only</span>
          </div>
        </div>

        {/* Password card — lets Microsoft SSO accounts set a usable local password */}
        <div style={{
          background: 'var(--surface-card)',
          border: '1px solid var(--border)',
          borderRadius: 10,
          padding: '16px 20px',
          marginBottom: 16,
        }}>
          <div style={{ fontSize: 17, fontWeight: 500, color: 'var(--text-heading)', marginBottom: 2 }}>
            Password
          </div>
          <div style={{
            fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)',
            marginBottom: 14, lineHeight: 1.5,
          }}>
            Set a local password to sign in without Microsoft
          </div>

          {passwordError && (
            <div style={{
              padding: '7px 11px', marginBottom: 10,
              background: 'rgba(244,63,94,0.08)',
              border: '1px solid rgba(244,63,94,0.2)',
              borderRadius: 6, color: '#f43f5e',
              fontSize: 15, fontFamily: 'var(--font-mono)',
            }}>{passwordError}</div>
          )}

          {passwordSaved && (
            <div style={{
              padding: '7px 11px', marginBottom: 10,
              background: 'rgba(16,185,129,0.08)',
              border: '1px solid rgba(16,185,129,0.2)',
              borderRadius: 6, color: '#10b981',
              fontSize: 15, fontFamily: 'var(--font-mono)',
            }}>Password updated</div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {([
              ['new password (min 6 characters)', newPassword, setNewPassword],
              ['repeat new password', confirmPassword, setConfirmPassword],
            ] as const).map(([placeholder, value, setter]) => (
              <input
                key={placeholder}
                type="password"
                placeholder={placeholder}
                value={value}
                onChange={e => setter(e.target.value)}
                style={{
                  padding: '9px 11px', background: 'var(--surface-input)',
                  border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)',
                  fontSize: 16, fontFamily: 'var(--font-mono)', outline: 'none',
                }}
                onFocus={e => { e.currentTarget.style.borderColor = 'rgba(var(--accent-rgb),0.32)' }}
                onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
              />
            ))}
            <button
              onClick={handlePasswordSave}
              disabled={passwordSaving || !newPassword}
              style={{
                padding: '10px 0', cursor: passwordSaving || !newPassword ? 'default' : 'pointer',
                background: passwordSaving || !newPassword ? 'rgba(var(--accent-rgb),0.07)' : 'rgba(var(--accent-rgb),0.12)',
                border: '1px solid rgba(var(--accent-rgb),0.28)',
                borderRadius: 8, color: 'var(--accent)',
                fontSize: 16, fontWeight: 700, letterSpacing: '0.04em',
                fontFamily: 'var(--font-mono)',
              }}
            >{passwordSaving ? 'SAVING…' : 'SET PASSWORD'}</button>
          </div>
        </div>

        {/* Admin: Manage Users */}
        {isAdmin && (
          <button
            onClick={() => navigate('/users')}
            style={{
              width: '100%', padding: '11px 0', cursor: 'pointer', marginBottom: 10,
              background: 'rgba(var(--accent-rgb),0.07)',
              border: '1px solid rgba(var(--accent-rgb),0.2)',
              borderRadius: 8, color: 'var(--accent)',
              fontSize: 16, fontWeight: 700, letterSpacing: '0.04em',
              transition: 'background 0.14s',
              fontFamily: 'var(--font-mono)',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(var(--accent-rgb),0.14)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(var(--accent-rgb),0.07)' }}
          >Manage users</button>
        )}

        {/* Logout */}
        <button
          onClick={logout}
          style={{
            width: '100%', padding: '11px 0', cursor: 'pointer',
            background: 'rgba(244,63,94,0.07)',
            border: '1px solid rgba(244,63,94,0.18)',
            borderRadius: 8, color: '#f43f5e',
            fontSize: 16, fontWeight: 700, letterSpacing: '0.04em',
            transition: 'background 0.14s',
            fontFamily: 'var(--font-mono)',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(244,63,94,0.14)' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(244,63,94,0.07)' }}
        >Sign out</button>
      </div>
    </div>
  )
}
