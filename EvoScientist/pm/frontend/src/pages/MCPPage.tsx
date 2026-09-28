import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'

export function MCPPage() {
  const qc = useQueryClient()
  const [tab, setTab] = useState<'marketplace' | 'installed'>('marketplace')
  const [tagFilter, setTagFilter] = useState('')

  const { data: marketplace } = useQuery({
    queryKey: ['mcp-marketplace', tagFilter],
    queryFn: () => api.mcpMarketplace(tagFilter || undefined),
  })
  const { data: installed } = useQuery({ queryKey: ['mcp-installed'], queryFn: () => api.mcpInstalled() })

  const install = useMutation({
    mutationFn: (name: string) => api.mcpInstall(name),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['mcp-marketplace'] }); qc.invalidateQueries({ queryKey: ['mcp-installed'] }) },
  })
  const remove = useMutation({
    mutationFn: (name: string) => api.mcpRemove(name),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['mcp-marketplace'] }); qc.invalidateQueries({ queryKey: ['mcp-installed'] }) },
  })

  const installedNames = new Set((installed?.servers ?? []).map(s => s.name))

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', padding: '32px 28px', maxWidth: 860, margin: '0 auto' }}>
      <h1 style={{ margin: '0 0 24px', fontSize: 30, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>MCP Servers</h1>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        <button onClick={() => setTab('marketplace')} style={{ cursor: 'pointer', padding: '7px 16px', background: tab === 'marketplace' ? 'rgba(99,102,241,0.15)' : 'transparent', border: tab === 'marketplace' ? '1px solid rgba(99,102,241,0.4)' : '1px solid var(--border)', borderRadius: 7, color: tab === 'marketplace' ? '#818cf8' : 'var(--text-dim)', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>MARKETPLACE</button>
        <button onClick={() => setTab('installed')} style={{ cursor: 'pointer', padding: '7px 16px', background: tab === 'installed' ? 'rgba(99,102,241,0.15)' : 'transparent', border: tab === 'installed' ? '1px solid rgba(99,102,241,0.4)' : '1px solid var(--border)', borderRadius: 7, color: tab === 'installed' ? '#818cf8' : 'var(--text-dim)', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>INSTALLED ({installed?.servers.length ?? 0})</button>
      </div>

      {tab === 'marketplace' && (
        <>
          {marketplace?.tags && marketplace.tags.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginBottom: 16 }}>
              <button onClick={() => setTagFilter('')} style={{ cursor: 'pointer', padding: '3px 8px', background: !tagFilter ? 'rgba(99,102,241,0.15)' : 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 5, color: !tagFilter ? '#818cf8' : 'var(--text-dim)', fontSize: 12, fontFamily: 'var(--font-mono)' }}>ALL</button>
              {marketplace.tags.map(t => (
                <button key={t} onClick={() => setTagFilter(t)} style={{ cursor: 'pointer', padding: '3px 8px', background: tagFilter === t ? 'rgba(99,102,241,0.15)' : 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 5, color: tagFilter === t ? '#818cf8' : 'var(--text-dim)', fontSize: 12, fontFamily: 'var(--font-mono)' }}>{t.toUpperCase()}</button>
              ))}
            </div>
          )}

          {(marketplace?.servers ?? []).map(s => (
            <div key={s.name} style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 18px', marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 20, fontWeight: 500, color: 'var(--text-heading)' }}>{s.label}</div>
                  <div style={{ fontSize: 14, color: 'var(--text-dim)', marginTop: 4 }}>{s.description}</div>
                  <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', padding: '2px 6px', background: 'var(--surface-input)', borderRadius: 3 }}>{s.transport}</span>
                    {s.tags.map(t => <span key={t} style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: '#10b981', padding: '2px 6px', background: 'rgba(16,185,129,0.08)', borderRadius: 3 }}>{t}</span>)}
                    {s.env_key && <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: '#f59e0b', padding: '2px 6px', background: 'rgba(245,158,11,0.08)', borderRadius: 3 }}>requires {s.env_key}</span>}
                  </div>
                </div>
                {s.installed ? (
                  <button onClick={() => remove.mutate(s.name)} disabled={remove.isPending} style={{ cursor: 'pointer', padding: '6px 14px', background: 'rgba(244,63,94,0.1)', border: '1px solid rgba(244,63,94,0.3)', borderRadius: 7, color: '#f43f5e', fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)', marginLeft: 12, whiteSpace: 'nowrap' }}>REMOVE</button>
                ) : (
                  <button onClick={() => install.mutate(s.name)} disabled={install.isPending} style={{ cursor: 'pointer', padding: '6px 14px', background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.28)', borderRadius: 7, color: '#10b981', fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)', marginLeft: 12, whiteSpace: 'nowrap' }}>INSTALL</button>
                )}
              </div>
            </div>
          ))}
        </>
      )}

      {tab === 'installed' && (
        (installed?.servers ?? []).length === 0 ? (
          <p style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 15 }}>No MCP servers installed.</p>
        ) : (
          (installed?.servers ?? []).map(s => (
            <div key={s.name} style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 18px', marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontSize: 20, fontWeight: 500, color: 'var(--text-heading)' }}>{s.name}</div>
                  <div style={{ fontSize: 14, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>{s.transport} {s.command ? `· ${s.command} ${s.args.join(' ')}` : ''} {s.url ?? ''}</div>
                </div>
                <button onClick={() => remove.mutate(s.name)} disabled={remove.isPending} style={{ cursor: 'pointer', padding: '6px 14px', background: 'rgba(244,63,94,0.1)', border: '1px solid rgba(244,63,94,0.3)', borderRadius: 7, color: '#f43f5e', fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>REMOVE</button>
              </div>
            </div>
          ))
        )
      )}
    </div>
  )
}
