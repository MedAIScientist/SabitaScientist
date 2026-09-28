import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, IntegrationStatus } from '../api'

const KIND_COLORS: Record<string, string> = {
  annotation: '#ff8015',
  imaging: '#8b5cf6',
  compute: '#10b981',
  identity: '#6366f1',
}

const KIND_MONOGRAM: Record<string, string> = {
  annotation: 'CV',
  imaging: 'PA',
  compute: 'JY',
  identity: 'ID',
}

export function AppsPage() {
  const { data: apps = [], isLoading, isFetching, refetch, error } = useQuery({
    queryKey: ['integrations'],
    queryFn: () => api.listIntegrations(),
    refetchInterval: 30_000,
  })

  const down = apps.filter(a => !a.up).length

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <div style={{ maxWidth: 960, margin: '0 auto', padding: '32px 28px' }}>

        <div style={{
          display: 'flex', justifyContent: 'space-between',
          alignItems: 'flex-start', marginBottom: 22, gap: 16,
        }}>
          <div>
            <h1 style={{
              margin: 0, fontSize: 30, fontWeight: 600,
              fontFamily: 'var(--font-mono)', color: 'var(--text-heading)',
            }}>Apps</h1>
            <p style={{
              margin: '4px 0 0', fontSize: 16, color: 'var(--text-dim)',
              fontFamily: 'var(--font-mono)',
            }}>
              {apps.length} SERVICE{apps.length !== 1 ? 'S' : ''}
              {down > 0 && <span style={{ color: '#f43f5e' }}> · {down} UNREACHABLE</span>}
            </p>
          </div>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            style={{
              cursor: isFetching ? 'default' : 'pointer', padding: '7px 16px',
              background: 'rgba(255,128,21,0.1)', border: '1px solid rgba(255,128,21,0.3)',
              borderRadius: 7, color: '#ff8015', fontSize: 15, fontWeight: 700,
              fontFamily: 'var(--font-mono)',
            }}
          >{isFetching ? 'CHECKING…' : 'CHECK AGAIN'}</button>
        </div>

        <div style={{
          padding: '10px 14px', marginBottom: 20,
          background: 'var(--surface-card)', border: '1px solid var(--border)',
          borderRadius: 8, fontSize: 16, color: 'var(--text-dim)', lineHeight: 1.55,
        }}>
          These tools run alongside Medai and share its sign-in. Each opens in a new
          tab — they are separate applications and cannot be embedded here.
        </div>

        {error && (
          <div style={{
            padding: '10px 14px', marginBottom: 16, background: 'rgba(244,63,94,0.08)',
            border: '1px solid rgba(244,63,94,0.2)', borderRadius: 7,
            color: '#f43f5e', fontSize: 18, fontFamily: 'var(--font-mono)',
          }}>
            Could not read service status. The apps may still be reachable directly.
          </div>
        )}

        {isLoading ? (
          <div style={{
            padding: 40, textAlign: 'center', color: 'var(--text-dim)',
            fontFamily: 'var(--font-mono)',
          }}>LOADING…</div>
        ) : (
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: 14,
          }}>
            {apps.map(app => <AppCard key={app.key} app={app} />)}
          </div>
        )}
      </div>
    </div>
  )
}

function AppCard({ app }: { app: IntegrationStatus }) {
  const accent = KIND_COLORS[app.kind] ?? '#6b7280'
  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      background: 'var(--surface-card)',
      border: '1px solid var(--border)',
      borderLeft: `3px solid ${app.up ? accent : '#6b7280'}`,
      borderRadius: '0 10px 10px 0',
      padding: '18px 20px',
      opacity: app.up ? 1 : 0.72,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 8, flexShrink: 0,
          background: `${accent}1f`, border: `1px solid ${accent}40`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: accent, fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
        }}>{KIND_MONOGRAM[app.kind] ?? '??'}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-heading)' }}>
            {app.name}
          </div>
          <div style={{
            fontSize: 13, color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)', letterSpacing: '0.06em',
          }}>{app.path}</div>
        </div>
        <StatusBadge app={app} />
      </div>

      <div style={{
        fontSize: 17, color: 'var(--text-2)', lineHeight: 1.5,
        flex: 1, marginBottom: 16,
      }}>{app.description}</div>

      <a
        href={app.path}
        target="_blank"
        rel="noopener noreferrer"
        style={{ textDecoration: 'none' }}
      >
        <button style={{
          width: '100%', padding: '9px 0', cursor: 'pointer',
          background: app.up ? 'rgba(255,128,21,0.12)' : 'var(--surface-input)',
          border: `1px solid ${app.up ? 'rgba(255,128,21,0.3)' : 'var(--border)'}`,
          borderRadius: 7, color: app.up ? '#ff8015' : 'var(--text-muted)',
          fontSize: 16, fontWeight: 700, letterSpacing: '0.1em',
          fontFamily: 'var(--font-mono)',
        }}>OPEN ↗</button>
      </a>

      {!app.up && (
        <div style={{
          fontSize: 13, color: '#f43f5e', fontFamily: 'var(--font-mono)',
          marginTop: 8, textAlign: 'center',
        }}>
          {app.http_status ? `UNREACHABLE (HTTP ${app.http_status})` : 'UNREACHABLE'}
        </div>
      )}
    </div>
  )
}

function StatusBadge({ app }: { app: IntegrationStatus }) {
  const color = app.up ? '#10b981' : '#f43f5e'
  return (
    <span
      title={app.up ? `Answered in ${app.latency_ms} ms` : 'No answer from this service'}
      style={{
        fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)',
        color, background: `${color}14`, border: `1px solid ${color}30`,
        borderRadius: 4, padding: '2px 8px', whiteSpace: 'nowrap', flexShrink: 0,
      }}
    >{app.up ? 'UP' : 'DOWN'}</span>
  )
}
