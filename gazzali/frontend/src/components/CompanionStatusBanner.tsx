import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api'

const DISMISS_KEY = 'pm_companion_down_dismissed'

/**
 * Tells the signed-in user when a cluster-hosted companion is not answering.
 *
 * CVAT, Curator, JupyterHub and Authentik are published as subpaths of this host and
 * served from the Kubernetes cluster. When that cluster's gateway stops answering, the
 * only trace used to be an nginx log line: users clicked through to a bare 502 and the
 * first anyone heard of it was a complaint. The status was already probed for the
 * System Health page; this puts it where people actually are.
 *
 * Dismissal is remembered per set of failing services, so a dismissed banner stays
 * dismissed while the same thing is broken, but a *new* service going down speaks up.
 */
export function CompanionStatusBanner() {
  // Same query key as the health page and the launcher: one probe, shared.
  const { data: apps = [] } = useQuery({
    queryKey: ['integrations'],
    queryFn: () => api.listIntegrations(),
    refetchInterval: 60_000,
  })

  // Kept in state, not read on every render: dismissing has to re-render, and a plain
  // sessionStorage write would not.
  const [dismissed, setDismissed] = useState<string>(() => {
    try {
      return sessionStorage.getItem(DISMISS_KEY) ?? ''
    } catch {
      return '' // private mode: showing the banner is the safer default
    }
  })

  const down = apps.filter(app => !app.up)
  const signature = down.map(app => app.key).sort().join(',')

  if (down.length === 0 || (signature && dismissed === signature)) return null

  const names = down.map(app => app.name)

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
        margin: '12px 16px 0', padding: '9px 12px', borderRadius: 8,
        background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.28)',
        color: '#f59e0b', fontSize: 14,
      }}
    >
      <span aria-hidden>⚠</span>
      <span style={{ color: 'var(--text-2)' }}>
        <strong style={{ color: '#f59e0b', fontWeight: 600 }}>
          {names.length === 1 ? `${names[0]} is not answering` : `${names.length} companion services are not answering`}
        </strong>
        {names.length > 1 && <> — {names.join(', ')}</>}.
        {' '}They run in the cluster, so this is not a problem with your account or this page.
      </span>
      <Link to="/health" style={{ color: '#f59e0b', fontSize: 13, marginLeft: 'auto', whiteSpace: 'nowrap' }}>
        System health →
      </Link>
      <button
        type="button"
        title="Dismiss until something else breaks"
        aria-label="Dismiss"
        onClick={() => {
          try { sessionStorage.setItem(DISMISS_KEY, signature) } catch { /* private mode */ }
          setDismissed(signature)
        }}
        style={{ background: 'none', border: 'none', color: '#f59e0b', cursor: 'pointer', fontSize: 15, padding: '0 2px' }}
      >
        ✕
      </button>
    </div>
  )
}
