import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth'

const NAV_ITEMS = [
  { path: '/projects', label: 'PROJECTS' },
  { path: '/labs', label: 'LABS' },
  { path: '/admissions', label: 'ADMISSIONS' },
  { path: '/users', label: 'USERS', adminOnly: true },
  { path: '/admin', label: 'ADMIN', adminOnly: true },
]

export function NavBar() {
  const { username, isAdmin, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <div style={{
      height: 48,
      background: 'var(--surface-header)',
      borderBottom: '1px solid var(--border)',
      display: 'flex', alignItems: 'center',
      padding: '0 28px', gap: 4,
      position: 'sticky', top: 0, zIndex: 20,
    }}>
      <img src="/sabita.jpg" alt="SABITA" style={{ height: 22, borderRadius: 3, marginRight: 8 }} />
      {NAV_ITEMS.filter(item => !item.adminOnly || isAdmin).map(item => {
        const active = location.pathname.startsWith(item.path)
        return (
          <button
            key={item.path}
            onClick={() => navigate(item.path)}
            style={{
              padding: '4px 12px', cursor: 'pointer', fontSize: 14, fontWeight: 700,
              fontFamily: 'var(--font-mono)', letterSpacing: '0.08em',
              background: active ? 'rgba(255,128,21,0.12)' : 'transparent',
              border: active ? '1px solid rgba(255,128,21,0.25)' : '1px solid transparent',
              borderRadius: 5, color: active ? '#ff8015' : 'var(--text-dim)',
              transition: 'background 0.12s, color 0.12s',
            }}
            onMouseEnter={e => { if (!active) { e.currentTarget.style.color = '#ff8015'; e.currentTarget.style.background = 'rgba(255,128,21,0.06)' } }}
            onMouseLeave={e => { if (!active) { e.currentTarget.style.color = 'var(--text-dim)'; e.currentTarget.style.background = 'transparent' } }}
          >
            {item.label}
          </button>
        )
      })}
      <div style={{ flex: 1 }} />
      <span style={{ fontSize: 14, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginRight: 8 }}>
        {username}
      </span>
      <button
        onClick={() => { logout(); navigate('/login') }}
        style={{
          padding: '3px 10px', cursor: 'pointer', fontSize: 14, fontFamily: 'var(--font-mono)',
          background: 'transparent', border: '1px solid var(--border)',
          borderRadius: 4, color: 'var(--text-muted)',
        }}
      >LOG OUT</button>
    </div>
  )
}
