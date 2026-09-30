import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api'

export function SystemHealthPage() {
  const { data: health } = useQuery({
    queryKey: ['system-health'],
    queryFn: () => api.systemHealth(),
    refetchInterval: 30_000,
  })
  const { data: apps = [] } = useQuery({
    queryKey: ['integrations'],
    queryFn: () => api.listIntegrations(),
    refetchInterval: 30_000,
  })

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', padding: '32px 28px', maxWidth: 900, margin: '0 auto' }}>
      <h1 style={{ margin: '0 0 24px', fontSize: 24, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>System Health</h1>

      <div style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '18px 20px', marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div><span style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-heading)' }}>LangGraph Dev</span>
            <div style={{ fontSize: 14, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>{health?.langgraph_dev?.url ?? '—'}</div></div>
          <span style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)', color: health?.langgraph_dev?.running ? '#10b981' : '#f43f5e', padding: '3px 8px', borderRadius: 3, background: health?.langgraph_dev?.running ? 'rgba(16,185,129,0.1)' : 'rgba(244,63,94,0.1)' }}>{health?.langgraph_dev?.running ? 'RUNNING' : 'OFFLINE'}</span>
        </div>
      </div>

      <div style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '18px 20px', marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div><span style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-heading)' }}>Skills</span>
            <div style={{ fontSize: 14, color: 'var(--text-dim)', marginTop: 2 }}>Installed Gazzali skills available to the agent</div></div>
          <span style={{ fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#818cf8' }}>{health?.skills_available ?? '—'}</span>
        </div>
      </div>

      <div style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '18px 20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div><span style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-heading)' }}>Agent Runner</span>
            <div style={{ fontSize: 14, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>PM agent runner service: runs drafting, research, code agents</div></div>
          <span style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#10b981', padding: '3px 8px', borderRadius: 3, background: 'rgba(16,185,129,0.1)' }}>Active</span>
        </div>
      </div>

      {/* Cluster-hosted companions live on subpaths of this host; a down card here
          means the subpath stopped answering, not that this app is unhealthy. */}
      {apps.length > 0 && (
        <>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
            margin: '24px 0 12px',
          }}>
            <h2 style={{
              margin: 0, fontSize: 16, fontWeight: 600,
              fontFamily: 'var(--font-mono)', color: 'var(--text-heading)',
            }}>Companion apps</h2>
            <Link
              to="/apps"
              style={{
                fontSize: 14, color: 'var(--accent)', fontFamily: 'var(--font-mono)',
                textDecoration: 'none', letterSpacing: '0.04em',
              }}
            >Open launcher →</Link>
          </div>

          {apps.map(app => (
            <div key={app.key} style={{
              background: 'var(--surface-card)', border: '1px solid var(--border)',
              borderRadius: 10, padding: '14px 20px', marginBottom: 10,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <span style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-heading)' }}>
                    {app.name}
                  </span>
                  <div style={{
                    fontSize: 14, color: 'var(--text-dim)',
                    fontFamily: 'var(--font-mono)', marginTop: 2,
                  }}>{app.path}</div>
                </div>
                <span style={{
                  fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)',
                  color: app.up ? '#10b981' : '#f43f5e',
                  padding: '3px 8px', borderRadius: 3,
                  background: app.up ? 'rgba(16,185,129,0.1)' : 'rgba(244,63,94,0.1)',
                }}>
                  {app.up ? `UP · ${app.latency_ms}ms` : app.http_status ? `DOWN · ${app.http_status}` : 'DOWN'}
                </span>
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  )
}
