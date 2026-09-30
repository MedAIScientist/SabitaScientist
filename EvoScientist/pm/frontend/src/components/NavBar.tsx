import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth'
import { useTheme } from '../theme'
import { api } from '../api'
import { CopilotPanel } from './CopilotPanel'

// ponytail: hand-drawn 24px stroke icons, swap for lucide-react if the set grows past ~30
const ICONS: Record<string, string> = {
  home: 'M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z',
  gauge: 'M4 18a8 8 0 1 1 16 0M12 18l4-6',
  folder: 'M3 6a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z',
  flask: 'M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3',
  paper: 'M6 3h9l4 4v14H6zM14 3v5h5M9 13h7M9 17h7',
  lab: 'M4 21V9l8-5 8 5v12M9 21v-6h6v6',
  pen: 'M4 20h4L19 9l-4-4L4 16zM13 7l4 4',
  users: 'M16 20v-1a4 4 0 0 0-8 0v1M12 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6M20 20v-1a3 3 0 0 0-2-3M17 5a3 3 0 0 1 0 6',
  route: 'M6 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4M18 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4M8 17h6a3 3 0 0 0 0-6h-4a3 3 0 0 1 0-6h6',
  chart: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
  check: 'M9 11l3 3 8-8M20 12v7a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h11',
  coin: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18M15 9h-4a2 2 0 0 0 0 4h2a2 2 0 0 1 0 4H9M12 6v2M12 16v2',
  calendar: 'M4 5h16v16H4zM4 10h16M8 3v4M16 3v4',
  shield: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z',
  inbox: 'M3 13l3-8h12l3 8v6H3zM3 13h5l1 2h6l1-2h5',
  grid: 'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z',
  person: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8M4 21a8 8 0 0 1 16 0',
  cog: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6M19 12l2-1-1-3-2 .5-1.5-1.5.5-2-3-1-1 2h-2l-1-2-3 1 .5 2L7 7.5 5 7 4 10l2 1v2l-2 1 1 3 2-.5L8.5 16 8 18l3 1 1-2h2l1 2 3-1-.5-2 1.5-1.5 2 .5 1-3-2-1z',
  help: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.7M12 17h.01',
  search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14M21 21l-5-5',
  spark: 'M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6',
  sun: 'M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8M12 2v2M12 20v2M4 12H2M22 12h-2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5',
  moon: 'M20 14A8 8 0 0 1 10 4a8 8 0 1 0 10 10',
  logout: 'M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 17l5-5-5-5M15 12H3',
  menu: 'M4 6h16M4 12h16M4 18h16',
  collapse: 'M15 6l-6 6 6 6',
  expand: 'M9 6l6 6-6 6',
}

export function Icon({ name, size = 18 }: { name: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden style={{ flexShrink: 0 }}>
      <path d={ICONS[name]} />
    </svg>
  )
}

type Role = 'student' | 'professor' | 'admin'
interface NavItem { path: string; label: string; icon: string; roles?: Role[]; adminOnly?: boolean }
interface NavGroup { title?: string; items: NavItem[] }

const NAV_GROUPS: NavGroup[] = [
  { items: [
    { path: '/home', label: 'Home', icon: 'home' },
    { path: '/professor', label: 'Dashboard', icon: 'gauge', roles: ['professor'] },
  ] },
  { title: 'Research', items: [
    { path: '/projects', label: 'Projects', icon: 'folder' },
    { path: '/research-items', label: 'Research items', icon: 'flask' },
    { path: '/publications', label: 'Papers', icon: 'paper' },
    { path: '/labs', label: 'Labs', icon: 'lab' },
  ] },
  { title: 'Supervision', items: [
    { path: '/weekly-update', label: 'Weekly update', icon: 'pen', roles: ['student', 'professor'] },
    { path: '/meeting', label: 'Weekly meeting', icon: 'users', roles: ['professor'] },
    { path: '/journey', label: 'Journey', icon: 'route', roles: ['student', 'professor'] },
    { path: '/supervision/reports', label: 'Reports', icon: 'chart', roles: ['professor', 'admin'] },
    { path: '/requirements', label: 'Requirements', icon: 'check', roles: ['professor', 'admin'] },
  ] },
  { title: 'Research office', items: [
    { path: '/grants', label: 'Grants', icon: 'coin' },
    { path: '/conferences', label: 'Conferences', icon: 'calendar' },
    { path: '/irb', label: 'Ethics (IRB)', icon: 'shield' },
    { path: '/admissions', label: 'Admissions', icon: 'inbox', roles: ['professor', 'admin'] },
  ] },
  { title: 'Tools', items: [
    { path: '/apps', label: 'Apps', icon: 'grid' },
  ] },
  { title: 'Administration', items: [
    { path: '/users', label: 'People', icon: 'person', adminOnly: true },
    { path: '/admin', label: 'System', icon: 'gauge', adminOnly: true },
  ] },
]

const FOOTER_ITEMS: NavItem[] = [
  { path: '/help', label: 'Help', icon: 'help' },
  { path: '/settings', label: 'Settings', icon: 'cog' },
]

const COLLAPSE_KEY = 'pm-sidebar-collapsed'
const readCollapsed = () => { try { return localStorage.getItem(COLLAPSE_KEY) === '1' } catch { return false } }

function useVisibleGroups(): NavGroup[] {
  const { isAdmin, role } = useAuth()
  return useMemo(() => NAV_GROUPS
    .map(g => ({ ...g, items: g.items.filter(i => {
      if (i.adminOnly) return isAdmin
      return !i.roles || isAdmin || i.roles.includes(role as Role)
    }) }))
    .filter(g => g.items.length > 0), [isAdmin, role])
}

/** Sidebar + scrollable main area. Pages render inside `main`, which is exactly one viewport tall. */
export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [copilotOpen, setCopilotOpen] = useState(false)
  const location = useLocation()

  useEffect(() => { try { localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0') } catch { /* private mode */ } }, [collapsed])
  useEffect(() => { setMobileOpen(false) }, [location.pathname])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPaletteOpen(o => !o) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="shell" data-collapsed={collapsed || undefined} data-mobile-open={mobileOpen || undefined}>
      <Sidebar
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed(c => !c)}
        onSearch={() => setPaletteOpen(true)}
        copilotOpen={copilotOpen}
        onToggleCopilot={() => setCopilotOpen(o => !o)}
      />
      <div className="shell-scrim" onClick={() => setMobileOpen(false)} />
      <main className="shell-main">
        <button className="shell-burger" aria-label="Open menu" onClick={() => setMobileOpen(true)}><Icon name="menu" /></button>
        {children}
      </main>
      {paletteOpen && <CommandPalette onClose={() => setPaletteOpen(false)} />}
      {copilotOpen && <CopilotPanel onClose={() => setCopilotOpen(false)} />}
    </div>
  )
}

function Sidebar({ collapsed, onToggleCollapse, onSearch, copilotOpen, onToggleCopilot }: {
  collapsed: boolean; onToggleCollapse: () => void; onSearch: () => void
  copilotOpen: boolean; onToggleCopilot: () => void
}) {
  const { username, role, isAdmin, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const location = useLocation()
  const groups = useVisibleGroups()
  const isMac = typeof navigator !== 'undefined' && /Mac/.test(navigator.platform)

  const link = (item: NavItem) => {
    const active = location.pathname === item.path || location.pathname.startsWith(item.path + '/')
    return (
      <a key={item.path} href={item.path} className="nav-link" aria-current={active ? 'page' : undefined}
        title={collapsed ? item.label : undefined}
        onClick={e => { if (e.metaKey || e.ctrlKey || e.button !== 0) return; e.preventDefault(); navigate(item.path) }}>
        <Icon name={item.icon} /><span className="nav-label">{item.label}</span>
      </a>
    )
  }

  return (
    <nav className="sidebar" aria-label="Main">
      <div className="sidebar-brand">
        <img src="/medipolLogo.png" alt="" />
        <span className="nav-label">EvoScientist</span>
        <button className="icon-btn sidebar-toggle" onClick={onToggleCollapse}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} title={collapsed ? 'Expand' : 'Collapse'}>
          <Icon name={collapsed ? 'expand' : 'collapse'} size={16} />
        </button>
      </div>

      <button className="nav-search" onClick={onSearch} title={collapsed ? 'Search' : undefined}>
        <Icon name="search" size={16} /><span className="nav-label">Search</span>
        <kbd className="nav-label">{isMac ? '⌘' : 'Ctrl'} K</kbd>
      </button>

      <div className="sidebar-scroll">
        {groups.map((g, i) => (
          <div key={g.title ?? i} className="nav-group">
            {g.title && <div className="nav-group-title">{g.title}</div>}
            {g.items.map(link)}
          </div>
        ))}
      </div>

      <div className="sidebar-footer">
        <button className="nav-link" data-active={copilotOpen || undefined} onClick={onToggleCopilot} title={collapsed ? 'AI copilot' : undefined}>
          <Icon name="spark" /><span className="nav-label">AI copilot</span>
        </button>
        {FOOTER_ITEMS.map(link)}
        <div className="nav-user">
          <a href="/profile" className="nav-avatar" title="Profile"
            onClick={e => { e.preventDefault(); navigate('/profile') }}>{(username || '?').slice(0, 1).toUpperCase()}</a>
          <div className="nav-label nav-user-meta">
            <div className="nav-user-name">{username}</div>
            <div className="nav-user-role">{isAdmin ? 'admin' : role}</div>
          </div>
          <button className="icon-btn nav-label-btn" onClick={toggleTheme}
            aria-label="Toggle theme" title={theme === 'dark' ? 'Light mode' : 'Dark mode'}>
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={16} /></button>
          <button className="icon-btn nav-label-btn" aria-label="Log out" title="Log out"
            onClick={() => { logout(); navigate('/login') }}><Icon name="logout" size={16} /></button>
        </div>
      </div>
    </nav>
  )
}

type Hit = { label: string; hint: string; path: string }

function CommandPalette({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const groups = useVisibleGroups()
  const [q, setQ] = useState('')
  const [remote, setRemote] = useState<Hit[]>([])
  const [sel, setSel] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  useEffect(() => {
    const term = q.trim()
    if (term.length < 2) { setRemote([]); return }
    let cancelled = false
    const t = setTimeout(async () => {
      try {
        const r: any = await api.globalSearch(term)
        if (cancelled) return
        const hits: Hit[] = []
        for (const cat of ['projects', 'tasks', 'experiments', 'publications'] as const) {
          for (const it of r[cat] || []) {
            hits.push({ label: it.name || it.title, hint: cat.slice(0, -1),
              path: it.project_id ? `/projects/${it.project_id}` : `/${cat}/${it.id}` })
          }
        }
        setRemote(hits)
      } catch { if (!cancelled) setRemote([]) }
    }, 200)
    return () => { cancelled = true; clearTimeout(t) }
  }, [q])

  const pages: Hit[] = useMemo(() => {
    const all = [...groups.flatMap(g => g.items.map(i => ({ label: i.label, hint: g.title ?? 'page', path: i.path }))),
      ...FOOTER_ITEMS.map(i => ({ label: i.label, hint: 'page', path: i.path })),
      { label: 'Profile', hint: 'page', path: '/profile' }]
    const term = q.trim().toLowerCase()
    return term ? all.filter(h => h.label.toLowerCase().includes(term)) : all
  }, [groups, q])

  const hits = [...pages, ...remote]
  useEffect(() => { setSel(0) }, [q, remote.length])

  const go = (h?: Hit) => { if (!h) return; onClose(); navigate(h.path) }

  return (
    <div className="palette-scrim" onMouseDown={onClose}>
      <div className="palette" role="dialog" aria-label="Search" onMouseDown={e => e.stopPropagation()}>
        <div className="palette-input">
          <Icon name="search" />
          <input ref={inputRef} value={q} onChange={e => setQ(e.target.value)}
            placeholder="Jump to a page or search projects, tasks, papers…"
            onKeyDown={e => {
              if (e.key === 'Escape') onClose()
              else if (e.key === 'ArrowDown') { e.preventDefault(); setSel(s => Math.min(s + 1, hits.length - 1)) }
              else if (e.key === 'ArrowUp') { e.preventDefault(); setSel(s => Math.max(s - 1, 0)) }
              else if (e.key === 'Enter') go(hits[sel])
            }} />
        </div>
        <ul className="palette-list">
          {hits.map((h, i) => (
            <li key={h.path + h.label + i} aria-selected={i === sel}
              onMouseEnter={() => setSel(i)} onClick={() => go(h)}>
              <span>{h.label}</span><span className="palette-hint">{h.hint}</span>
            </li>
          ))}
          {hits.length === 0 && <li className="palette-empty">No results</li>}
        </ul>
      </div>
    </div>
  )
}
