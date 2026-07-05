import { useState, useRef, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth'
import { api } from '../api'

const NAV_ITEMS = [
  { path: '/projects', label: 'PROJECTS' },
  { path: '/labs', label: 'LABS' },
  { path: '/publications', label: 'PAPERS' },
  { path: '/grants', label: 'GRANTS' },
  { path: '/analytics', label: 'ANALYTICS' },
  { path: '/admissions', label: 'ADMISSIONS' },
  { path: '/users', label: 'USERS', adminOnly: true },
  { path: '/admin', label: 'ADMIN', adminOnly: true },
]

export function NavBar() {
  const { username, isAdmin, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any>(null)
  const searchRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!searchOpen) { setSearchQuery(''); setSearchResults(null) }
  }, [searchOpen])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) setSearchOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  async function handleSearch() {
    if (!searchQuery.trim()) return
    try { setSearchResults(await api.globalSearch(searchQuery.trim())) }
    catch { setSearchResults(null) }
  }

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
          <button key={item.path} onClick={() => navigate(item.path)} style={{
            padding: '4px 12px', cursor: 'pointer', fontSize: 14, fontWeight: 700,
            fontFamily: 'var(--font-mono)', letterSpacing: '0.08em',
            background: active ? 'rgba(255,128,21,0.12)' : 'transparent',
            border: active ? '1px solid rgba(255,128,21,0.25)' : '1px solid transparent',
            borderRadius: 5, color: active ? '#ff8015' : 'var(--text-dim)',
            transition: 'background 0.12s, color 0.12s',
          }}
            onMouseEnter={e => { if (!active) { e.currentTarget.style.color = '#ff8015'; e.currentTarget.style.background = 'rgba(255,128,21,0.06)' } }}
            onMouseLeave={e => { if (!active) { e.currentTarget.style.color = 'var(--text-dim)'; e.currentTarget.style.background = 'transparent' } }}
          >{item.label}</button>
        )
      })}
      <div style={{ flex: 1 }} />
      <div ref={searchRef} style={{ position: 'relative' }}>
        <input
          value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
          onFocus={() => setSearchOpen(true)}
          onKeyDown={e => { if (e.key === 'Enter') handleSearch() }}
          placeholder="🔍 Search..."
          style={{
            width: searchOpen ? 200 : 120, padding: '3px 8px', fontSize: 14,
            background: 'var(--surface-input)', border: '1px solid var(--border)',
            borderRadius: 4, color: 'var(--text)', outline: 'none',
            transition: 'width 0.2s', fontFamily: 'var(--font-mono)',
          }}
        />
        {searchOpen && searchResults && (
          <div style={{
            position: 'absolute', top: '100%', right: 0, width: 320, marginTop: 4,
            background: 'var(--surface-panel)', border: '1px solid var(--border)',
            borderRadius: 8, padding: 8, maxHeight: 300, overflowY: 'auto', zIndex: 100,
          }}>
            {(['projects', 'tasks', 'experiments', 'publications'] as const).map(cat => {
              const items = searchResults[cat] || []
              if (items.length === 0) return null
              return (
                <div key={cat} style={{ marginBottom: 6 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', marginBottom: 2, letterSpacing: '0.06em' }}>{cat.toUpperCase()}</div>
                  {items.map((item: any, i: number) => (
                    <div key={i} onClick={() => { setSearchOpen(false); navigate(item.project_id ? `/projects/${item.project_id}` : `/${cat}/${item.id}`) }} style={{
                      padding: '3px 6px', cursor: 'pointer', borderRadius: 4, fontSize: 15,
                      color: 'var(--text-2)', transition: 'background 0.1s',
                    }}
                      onMouseEnter={e => { e.currentTarget.style.background = 'var(--surface-input)' }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
                    >{item.name || item.title}</div>
                  ))}
                </div>
              )
            })}
            {!searchResults.projects?.length && !searchResults.tasks?.length && !searchResults.experiments?.length && !searchResults.publications?.length && (
              <div style={{ fontSize: 15, color: 'var(--text-dim)', padding: 8 }}>No results found</div>
            )}
          </div>
        )}
      </div>
      <span style={{ fontSize: 14, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginLeft: 8 }}>
        {username}
      </span>
      <button onClick={() => { logout(); navigate('/login') }} style={{
        padding: '3px 10px', cursor: 'pointer', fontSize: 14, fontFamily: 'var(--font-mono)',
        background: 'transparent', border: '1px solid var(--border)',
        borderRadius: 4, color: 'var(--text-muted)',
      }}>LOG OUT</button>
    </div>
  )
}
