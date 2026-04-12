import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { useTheme } from '../theme'

export function ProfilePage() {
  const { username, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()

  const isDark = theme === 'dark'

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
          <button
            onClick={() => navigate(-1)}
            style={{
              cursor: 'pointer',
              background: 'var(--surface-input)',
              border: '1px solid var(--border)',
              borderRadius: 6, color: 'var(--text-muted)',
              padding: '3px 9px', fontSize: 15, lineHeight: 1,
              transition: 'color 0.15s, border-color 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = '#ff8015'; e.currentTarget.style.borderColor = 'rgba(255,128,21,0.3)' }}
            onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.borderColor = 'var(--border)' }}
          >←</button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <img src="/sabita.jpg" alt="SABITA" style={{ height: 26, borderRadius: 4, display: 'block' }} />
            <span style={{ color: 'var(--text-dim)', fontSize: 13, fontFamily: 'var(--font-mono)' }}>/</span>
            <span style={{ color: '#ff8015', fontSize: 14, fontFamily: 'var(--font-mono)' }}>profile</span>
          </div>
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
            fontSize: 25, fontWeight: 700, color: '#fff',
            fontFamily: 'var(--font-mono)',
            boxShadow: '0 0 20px rgba(255,128,21,0.25)',
          }}>
            {username?.[0]?.toUpperCase() ?? '?'}
          </div>
          <div>
            <div style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)' }}>
              {username}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2, letterSpacing: '0.06em' }}>
              RESEARCHER
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
              <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-heading)', marginBottom: 2 }}>
                Appearance
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                {isDark ? 'DARK MODE' : 'LIGHT MODE'}
              </div>
            </div>
            <button
              onClick={toggleTheme}
              title={`Switch to ${isDark ? 'light' : 'dark'} mode`}
              style={{
                width: 52, height: 28, borderRadius: 14,
                border: 'none', cursor: 'pointer',
                background: isDark ? 'rgba(255,128,21,0.15)' : 'rgba(255,128,21,0.25)',
                position: 'relative',
                transition: 'background 0.2s',
                flexShrink: 0,
                outline: '1px solid rgba(255,128,21,0.3)',
              }}
              aria-pressed={!isDark}
            >
              {/* Track label */}
              <span style={{
                position: 'absolute', top: '50%', transform: 'translateY(-50%)',
                fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 700,
                letterSpacing: '0.04em',
                left: isDark ? 'auto' : 8,
                right: isDark ? 8 : 'auto',
                color: '#ff8015',
                opacity: 0.8,
              }}>
                {isDark ? '🌙' : '☀'}
              </span>
              {/* Thumb */}
              <span style={{
                position: 'absolute', top: 4,
                left: isDark ? 4 : 24,
                width: 20, height: 20, borderRadius: '50%',
                background: isDark ? '#ff8015' : '#f59e0b',
                boxShadow: isDark ? '0 0 8px rgba(255,128,21,0.5)' : '0 0 8px rgba(245,158,11,0.5)',
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
              <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-heading)', marginBottom: 2 }}>
                Username
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                {username}
              </div>
            </div>
            <span style={{
              fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
              letterSpacing: '0.06em',
            }}>READ-ONLY</span>
          </div>
        </div>

        {/* Logout */}
        <button
          onClick={logout}
          style={{
            width: '100%', padding: '11px 0', cursor: 'pointer',
            background: 'rgba(244,63,94,0.07)',
            border: '1px solid rgba(244,63,94,0.18)',
            borderRadius: 8, color: '#f43f5e',
            fontSize: 11, fontWeight: 700, letterSpacing: '0.1em',
            transition: 'background 0.14s',
            fontFamily: 'var(--font-mono)',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(244,63,94,0.14)' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(244,63,94,0.07)' }}
        >SIGN OUT</button>
      </div>
    </div>
  )
}
