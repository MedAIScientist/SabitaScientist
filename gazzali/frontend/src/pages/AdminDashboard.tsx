import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

interface AdminStats {
  labs: number; users: number; projects: number; tasks: number
  experiments: number; assists: number; admissions: number
  lab_details: { id: string; name: string; department: string; university: string; member_count: number; project_count: number }[]
}

export function AdminDashboard() {
  const { token, isAdmin } = useAuth()
  const navigate = useNavigate()
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isAdmin) { navigate('/projects', { replace: true }); return }
    load()
  }, [isAdmin])

  async function load() {
    setLoading(true)
    try {
      const resp = await fetch('/api/v1/admin/stats', {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!resp.ok) throw new Error(await resp.text())
      setStats(await resp.json())
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load stats')
    } finally {
      setLoading(false)
    }
  }

  if (!isAdmin) return null

  const card: React.CSSProperties = {
    background: 'var(--surface-card)', border: '1px solid var(--border)',
    borderRadius: 10, padding: '18px 20px', textAlign: 'center',
  }
  const value: React.CSSProperties = {
    fontSize: 28, fontWeight: 700, color: 'var(--accent)', fontFamily: 'var(--font-mono)',
  }
  const label: React.CSSProperties = {
    fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 4, letterSpacing: '0.04em',
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <div className="page-header" style={{ maxWidth: 1100, margin: '0 auto', padding: '28px 32px 0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <h1 className="page-title">System administration</h1>
        </div>
        <span style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', background: 'rgba(var(--accent-rgb),0.1)', padding: '2px 8px', borderRadius: 4, border: '1px solid rgba(var(--accent-rgb),0.2)' }}>Admin</span>
      </div>

      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0 32px 40px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 16 }}>Loading…</div>
        ) : error ? (
          <div style={{ color: '#f43f5e', fontFamily: 'var(--font-mono)', fontSize: 16 }}>{error}</div>
        ) : stats ? (
          <>
            <h1 style={{ margin: '0 0 24px', fontSize: 24, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>
              System Overview
            </h1>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 32 }}>
              <div style={card}><div style={value}>{stats.labs}</div><div style={label}>Labs</div></div>
              <div style={card}><div style={value}>{stats.users}</div><div style={label}>Users</div></div>
              <div style={card}><div style={value}>{stats.projects}</div><div style={label}>Projects</div></div>
              <div style={card}><div style={value}>{stats.tasks}</div><div style={label}>Tasks</div></div>
              <div style={card}><div style={value}>{stats.experiments}</div><div style={label}>Experiments</div></div>
              <div style={card}><div style={value}>{stats.assists}</div><div style={label}>AI assists</div></div>
              <div style={card}><div style={value}>{stats.admissions}</div><div style={label}>Admissions</div></div>
            </div>

            <h2 style={{ margin: '0 0 16px', fontSize: 20, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>
              Labs
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {stats.lab_details.map(lab => (
                <div key={lab.id} style={{
                  background: 'var(--surface-card)', border: '1px solid var(--border)',
                  borderRadius: 10, padding: '14px 18px',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}>
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-heading)' }}>{lab.name}</div>
                    <div style={{ fontSize: 15, color: 'var(--text-dim)', marginTop: 2 }}>{lab.department}{lab.department && lab.university ? ' · ' : ''}{lab.university}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 16, fontFamily: 'var(--font-mono)', fontSize: 15, color: 'var(--text-dim)' }}>
                    <span>{lab.member_count} members</span>
                    <span>{lab.project_count} projects</span>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
