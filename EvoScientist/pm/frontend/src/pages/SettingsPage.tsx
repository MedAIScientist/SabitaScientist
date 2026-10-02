import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AnalyticsPage } from './AnalyticsPage'
import { AiSetupCard } from '../components/AiSetupCard'
import { api } from '../api'

function HealthTab() {
  const { data: h } = useQuery({ queryKey: ['set-health'], queryFn: () => api.systemHealth(), refetchInterval: 30_000 })
  return (
    <div>
      <AiSetupCard health={h} />

      <div style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '14px 16px', marginBottom: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div><span style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-heading)' }}>Skills</span><div style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 1 }}>Installed Gazzali skills</div></div>
          <span style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#818cf8' }}>{h?.skills_available ?? '—'}</span>
        </div>
      </div>
      <div style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '14px 16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div><span style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-heading)' }}>Agent Runner</span><div style={{ fontSize: 13, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 1 }}>PM drafting/research agents</div></div>
          <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#10b981', padding: '2px 7px', borderRadius: 3, background: 'rgba(16,185,129,0.1)' }}>Active</span>
        </div>
      </div>
    </div>
  )
}

function AnalyticsTab() {
  // The same data as /analytics. This tab used to read a health field that no longer
  // exists (langgraph_dev) and crashed on render.
  return <AnalyticsPage embedded />
}

export function SettingsPage() {
  const [tab, setTab] = useState<'health' | 'analytics'>('health')

  const tabs = [
    { key: 'health', label: 'Health' },
    { key: 'analytics', label: 'Analytics' },
  ]

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', padding: '32px 28px', maxWidth: 860, margin: '0 auto' }}>
      <h1 style={{ margin: '0 0 24px', fontSize: 24, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>Settings</h1>

      <div style={{ display: 'flex', gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
        {tabs.map(t => (
          <button key={t.key} onClick={() => setTab(t.key as typeof tab)} style={{ cursor: 'pointer', padding: '5px 12px', background: tab === t.key ? 'rgba(99,102,241,0.15)' : 'transparent', border: tab === t.key ? '1px solid rgba(99,102,241,0.4)' : '1px solid var(--border)', borderRadius: 6, color: tab === t.key ? '#818cf8' : 'var(--text-dim)', fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{t.label}</button>
        ))}
      </div>

      {tab === 'health' && <HealthTab />}
      {tab === 'analytics' && <AnalyticsTab />}
    </div>
  )
}
