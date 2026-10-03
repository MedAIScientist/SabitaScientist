import type { ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

const TABS = [
  { suffix: '', label: 'Board' },
  { suffix: '/experiments', label: 'Experiments' },
  { suffix: '/data', label: 'Data' },
  { suffix: '/report', label: 'Report' },
]

/** Shared header for every /projects/:id/* page: breadcrumb, section tabs, page-specific actions. */
export function ProjectHeader({ projectId, name, actions, children }: {
  projectId: string; name?: string; actions?: ReactNode; children?: ReactNode
}) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const base = `/projects/${projectId}`
  const go = (e: React.MouseEvent, to: string) => {
    if (e.metaKey || e.ctrlKey || e.button !== 0) return
    e.preventDefault(); navigate(to)
  }

  return (
    <div className="project-header">
      <div className="project-header-top">
        <div style={{ minWidth: 0 }}>
          <div className="crumbs">
            <a href="/projects" onClick={e => go(e, '/projects')}>Projects</a>
            <span aria-hidden>/</span>
          </div>
          <h1 className="page-title" style={{ fontSize: 20 }}>{name ?? '…'}</h1>
        </div>
        {actions && <div className="page-actions">{actions}</div>}
      </div>
      <nav className="tabs" aria-label="Project sections">
        {TABS.map(t => {
          const to = base + t.suffix
          return (
            <a key={t.label} href={to} className="tab" aria-current={pathname === to ? 'page' : undefined}
              onClick={e => go(e, to)}>{t.label}</a>
          )
        })}
      </nav>
      {children}
    </div>
  )
}
