import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'

function ModelTab() {
  const { data: models } = useQuery({ queryKey: ['models'], queryFn: () => api.listModels() })
  const { data: current } = useQuery({ queryKey: ['current-model'], queryFn: () => api.currentModel() })
  const select = useMutation({ mutationFn: (args: { model: string; provider?: string }) => api.selectModel(args.model, args.provider) })
  const [filter, setFilter] = useState('')

  const query = filter.toLowerCase()
  const filtered = models?.providers.map(p => ({
    ...p,
    models: p.models.filter(m => m.short_name.includes(query) || m.model_id.includes(query)),
  })).filter(p => p.models.length > 0)

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center' }}>
        <span style={{ fontSize: 16, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>Current: <b style={{ color: 'var(--text-heading)' }}>{current?.current_model ?? current?.default_model ?? '—'}</b></span>
        {select.isPending && <span style={{ color: 'var(--text-dim)', fontSize: 14 }}>switching...</span>}
        {select.isSuccess && <span style={{ color: '#10b981', fontSize: 14 }}>switched</span>}
        {select.isError && <span style={{ color: '#f43f5e', fontSize: 14 }}>failed</span>}
      </div>
      <input value={filter} onChange={e => setFilter(e.target.value)} placeholder="Filter models..." style={{ width: '100%', padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 16, outline: 'none', boxSizing: 'border-box', marginBottom: 12, fontFamily: 'var(--font-mono)' }} />
      <div style={{ maxHeight: 400, overflowY: 'auto' }}>
        {filtered?.map(p => (
          <div key={p.name} style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', marginBottom: 6, letterSpacing: '0.04em' }}>{p.name.toUpperCase()}</div>
            {p.models.map(m => {
              const isActive = m.short_name === current?.current_model
              return (
                <div key={m.short_name} onClick={() => select.mutate({ model: m.short_name, provider: p.name })} style={{
                  cursor: 'pointer', padding: '6px 10px', borderRadius: 6, marginBottom: 2,
                  background: isActive ? 'rgba(99,102,241,0.12)' : 'transparent',
                  border: isActive ? '1px solid rgba(99,102,241,0.25)' : '1px solid transparent',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}
                  onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'var(--surface-input)' }}
                  onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent' }}>
                  <span style={{ fontSize: 16, color: isActive ? '#818cf8' : 'var(--text-heading)', fontWeight: isActive ? 600 : 400 }}>{m.short_name}</span>
                  <span style={{ fontSize: 13, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>{m.model_id}</span>
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}

function SystemPromptTab() {
  const { data: sp, isLoading } = useQuery({ queryKey: ['system-prompt'], queryFn: () => api.systemPrompt() })
  const [expanded, setExpanded] = useState(false)

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>Length: <b>{sp?.length?.toLocaleString() ?? '—'}</b> chars</span>
        <button onClick={() => setExpanded(f => !f)} style={{ cursor: 'pointer', padding: '4px 10px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 5, color: 'var(--text-dim)', fontSize: 13, fontFamily: 'var(--font-mono)' }}>{expanded ? 'Collapse' : 'Expand'}</button>
      </div>
      {isLoading ? <p style={{ color: 'var(--text-dim)' }}>Loading...</p> : (
        <pre style={{
          background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7,
          padding: 14, fontSize: 13, lineHeight: 1.5, overflow: 'auto', whiteSpace: 'pre-wrap',
          maxHeight: expanded ? 'none' : 400, color: 'var(--text)', fontFamily: 'var(--font-code)',
          margin: 0,
        }}>{(sp?.system_prompt ?? '').slice(0, expanded ? undefined : 5000)}</pre>
      )}
    </div>
  )
}

function CronTab() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false); const [cName, setCName] = useState(''); const [cron, setCron] = useState(''); const [cPrompt, setCPrompt] = useState('')

  const { data: scheds } = useQuery({ queryKey: ['schedules'], queryFn: () => api.listSchedules() })

  const create = useMutation({
    mutationFn: () => api.createSchedule(cName, cron, cPrompt),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['schedules'] }); setShowForm(false); setCName(''); setCron(''); setCPrompt('') },
  })
  const toggle = useMutation({
    mutationFn: (args: { id: string; enabled: boolean }) => api.toggleSchedule(args.id, args.enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schedules'] }),
  })
  const del = useMutation({
    mutationFn: (id: string) => api.deleteSchedule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schedules'] }),
  })

  return (
    <div>
      <button onClick={() => setShowForm(f => !f)} style={{ cursor: 'pointer', padding: '7px 16px', background: 'rgba(var(--accent-rgb),0.1)', border: '1px solid rgba(var(--accent-rgb),0.3)', borderRadius: 7, color: 'var(--accent)', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)', marginBottom: 12 }}>+ New schedule</button>
      {showForm && (
        <form onSubmit={e => { e.preventDefault(); create.mutate() }} style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: 16, marginBottom: 12 }}>
          <input value={cName} onChange={e => setCName(e.target.value)} required placeholder="Name (e.g. weekly-lit-review)" style={{ width: '100%', padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 16, outline: 'none', boxSizing: 'border-box', marginBottom: 8, fontFamily: 'var(--font-mono)' }} />
          <input value={cron} onChange={e => setCron(e.target.value)} required placeholder="Cron expression (e.g. 0 9 * * 1)" style={{ width: '100%', padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 16, outline: 'none', boxSizing: 'border-box', marginBottom: 8, fontFamily: 'var(--font-mono)' }} />
          <textarea value={cPrompt} onChange={e => setCPrompt(e.target.value)} required placeholder="Prompt sent to the scheduler agent on each trigger" rows={3} style={{ width: '100%', padding: '9px 12px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 15, outline: 'none', boxSizing: 'border-box', fontFamily: 'var(--font-mono)', resize: 'vertical', marginBottom: 8 }} />
          <button type="submit" disabled={create.isPending} style={{ cursor: 'pointer', padding: '7px 16px', background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.28)', borderRadius: 7, color: '#10b981', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>Create</button>
        </form>
      )}
      {(scheds?.schedules ?? []).length === 0 ? (
        <p style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 15 }}>No scheduled tasks. Create one above.</p>
      ) : (
        (scheds?.schedules ?? []).map(s => (
          <div key={s.cron_id} style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px', marginBottom: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-heading)' }}>{s.name}</div>
                <div style={{ fontSize: 14, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>{s.schedule}</div>
                <div style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 4, whiteSpace: 'pre-wrap' }}>{s.prompt.slice(0, 200)}</div>
              </div>
              <div style={{ display: 'flex', gap: 6, marginLeft: 12, alignItems: 'center' }}>
                <button onClick={() => toggle.mutate({ id: s.cron_id, enabled: !s.enabled })} style={{ cursor: 'pointer', padding: '4px 10px', background: s.enabled ? 'rgba(16,185,129,0.1)' : 'rgba(244,63,94,0.1)', border: '1px solid var(--border)', borderRadius: 5, color: s.enabled ? '#10b981' : '#f43f5e', fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{s.enabled ? 'ON' : 'Off'}</button>
                <button onClick={() => del.mutate(s.cron_id)} style={{ cursor: 'pointer', padding: '4px 10px', background: 'rgba(244,63,94,0.1)', border: '1px solid rgba(244,63,94,0.3)', borderRadius: 5, color: '#f43f5e', fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>Del</button>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  )
}

function McpTab() {
  const [tagFilter, setTagFilter] = useState('')
  const qc = useQueryClient()
  const { data: marketplace } = useQuery({ queryKey: ['set-mcp-marketplace', tagFilter], queryFn: () => api.mcpMarketplace(tagFilter || undefined) })
  const { data: installed } = useQuery({ queryKey: ['set-mcp-installed'], queryFn: () => api.mcpInstalled() })
  const install = useMutation({ mutationFn: (n: string) => api.mcpInstall(n), onSuccess: () => { qc.invalidateQueries({ queryKey: ['set-mcp-marketplace'] }); qc.invalidateQueries({ queryKey: ['set-mcp-installed'] }) } })
  const remove = useMutation({ mutationFn: (n: string) => api.mcpRemove(n), onSuccess: () => { qc.invalidateQueries({ queryKey: ['set-mcp-marketplace'] }); qc.invalidateQueries({ queryKey: ['set-mcp-installed'] }) } })
  const [tab2, setTab2] = useState<'marketplace' | 'installed'>('marketplace')
  const installedNames = new Set((installed?.servers ?? []).map(s => s.name))
  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button onClick={() => setTab2('marketplace')} style={{ cursor: 'pointer', padding: '5px 12px', background: tab2 === 'marketplace' ? 'rgba(99,102,241,0.15)' : 'transparent', border: tab2 === 'marketplace' ? '1px solid rgba(99,102,241,0.4)' : '1px solid var(--border)', borderRadius: 6, color: tab2 === 'marketplace' ? '#818cf8' : 'var(--text-dim)', fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>Marketplace</button>
        <button onClick={() => setTab2('installed')} style={{ cursor: 'pointer', padding: '5px 12px', background: tab2 === 'installed' ? 'rgba(99,102,241,0.15)' : 'transparent', border: tab2 === 'installed' ? '1px solid rgba(99,102,241,0.4)' : '1px solid var(--border)', borderRadius: 6, color: tab2 === 'installed' ? '#818cf8' : 'var(--text-dim)', fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>INSTALLED ({installed?.servers.length ?? 0})</button>
      </div>
      {tab2 === 'marketplace' && (
        <>
          {marketplace?.tags && marketplace.tags.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginBottom: 12 }}>
              <button onClick={() => setTagFilter('')} style={{ cursor: 'pointer', padding: '2px 7px', background: !tagFilter ? 'rgba(99,102,241,0.15)' : 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 4, color: !tagFilter ? '#818cf8' : 'var(--text-dim)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>All</button>
              {marketplace.tags.map(t => (
                <button key={t} onClick={() => setTagFilter(t)} style={{ cursor: 'pointer', padding: '2px 7px', background: tagFilter === t ? 'rgba(99,102,241,0.15)' : 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 4, color: tagFilter === t ? '#818cf8' : 'var(--text-dim)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>{t.toUpperCase()}</button>
              ))}
            </div>
          )}
          {(marketplace?.servers ?? []).map(s => (
            <div key={s.name} style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px', marginBottom: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-heading)' }}>{s.label}</div>
                  <div style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 2 }}>{s.description}</div>
                  <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', padding: '1px 5px', background: 'var(--surface-input)', borderRadius: 2 }}>{s.transport}</span>
                    {s.tags.map(t => <span key={t} style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: '#10b981', padding: '1px 5px', background: 'rgba(16,185,129,0.08)', borderRadius: 2 }}>{t}</span>)}
                  </div>
                </div>
                {s.installed ? (
                  <button onClick={() => remove.mutate(s.name)} style={{ cursor: 'pointer', padding: '4px 10px', background: 'rgba(244,63,94,0.1)', border: '1px solid rgba(244,63,94,0.3)', borderRadius: 5, color: '#f43f5e', fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)', marginLeft: 10, whiteSpace: 'nowrap' }}>Remove</button>
                ) : (
                  <button onClick={() => install.mutate(s.name)} style={{ cursor: 'pointer', padding: '4px 10px', background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.28)', borderRadius: 5, color: '#10b981', fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)', marginLeft: 10, whiteSpace: 'nowrap' }}>Install</button>
                )}
              </div>
            </div>
          ))}
        </>
      )}
      {tab2 === 'installed' && (installed?.servers ?? []).length === 0 ? (
        <p style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 14 }}>No MCP servers installed.</p>
      ) : (
        (installed?.servers ?? []).map(s => (
          <div key={s.name} style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px', marginBottom: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-heading)' }}>{s.name}</div>
                <div style={{ fontSize: 13, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 1 }}>{s.transport} {s.command ? `· ${s.command}` : ''}</div>
              </div>
              <button onClick={() => remove.mutate(s.name)} style={{ cursor: 'pointer', padding: '4px 10px', background: 'rgba(244,63,94,0.1)', border: '1px solid rgba(244,63,94,0.3)', borderRadius: 5, color: '#f43f5e', fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>Remove</button>
            </div>
          </div>
        ))
      )}
    </div>
  )
}

function MemoryTab() {
  const [pid, setPid] = useState('')
  const [sq, setSq] = useState('')
  const [showRec, setShowRec] = useState(false); const [rt, setRt] = useState(''); const [rb, setRb] = useState('')
  const obs = useQuery({ queryKey: ['set-obs', pid], queryFn: () => api.listObservations(pid), enabled: !!pid })
  const search = useQuery({ queryKey: ['set-obs-search', pid, sq], queryFn: () => api.searchObservations(pid, sq), enabled: !!pid && sq.length >= 2 })
  const record = useMutation({ mutationFn: () => api.recordObservation(pid, rt, rb || undefined), onSuccess: () => { obs.refetch(); setShowRec(false); setRt(''); setRb('') } })
  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
        <input value={pid} onChange={e => setPid(e.target.value)} placeholder="Project ID" style={{ flex: 1, padding: '7px 10px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontSize: 15, outline: 'none', fontFamily: 'var(--font-mono)' }} />
        <button onClick={() => setShowRec(f => !f)} style={{ cursor: 'pointer', padding: '5px 12px', background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.28)', borderRadius: 6, color: '#10b981', fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>+ Record</button>
      </div>
      {showRec && (
        <form onSubmit={e => { e.preventDefault(); record.mutate() }} style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
          <input value={rt} onChange={e => setRt(e.target.value)} required placeholder="Title" style={{ width: '100%', padding: '7px 10px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontSize: 15, outline: 'none', boxSizing: 'border-box', marginBottom: 6 }} />
          <textarea value={rb} onChange={e => setRb(e.target.value)} placeholder="Body" rows={3} style={{ width: '100%', padding: '7px 10px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontSize: 14, outline: 'none', boxSizing: 'border-box', fontFamily: 'var(--font-mono)', resize: 'vertical', marginBottom: 6 }} />
          <button type="submit" style={{ cursor: 'pointer', padding: '5px 12px', background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.28)', borderRadius: 6, color: '#10b981', fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>Save</button>
        </form>
      )}
      {pid && (
        <>
          <input value={sq} onChange={e => setSq(e.target.value)} placeholder="Search observations..." style={{ width: '100%', padding: '7px 10px', background: 'var(--surface-input)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontSize: 15, outline: 'none', boxSizing: 'border-box', marginBottom: 10, fontFamily: 'var(--font-mono)' }} />
          {sq.length >= 2 && search.data && search.data.results.length > 0 && search.data.results.map(h => (
            <div key={h.id} style={{ background: 'var(--surface-card)', border: '1px solid rgba(99,102,241,0.3)', borderRadius: 8, padding: '10px 14px', marginBottom: 4 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-heading)' }}>{h.title}</span>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>{h.score.toFixed(3)}</span>
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 2, whiteSpace: 'pre-wrap' }}>{h.body.slice(0, 200)}</div>
            </div>
          ))}
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-dim)', margin: '10px 0 6px', fontFamily: 'var(--font-mono)' }}>ALL ({obs.data?.total ?? 0})</div>
          {(obs.data?.observations ?? []).map(o => (
            <div key={o.id} style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px', marginBottom: 4 }}>
              <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-heading)' }}>{o.title}</div>
              <div style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 2, whiteSpace: 'pre-wrap' }}>{o.body.slice(0, 200)}</div>
            </div>
          ))}
        </>
      )}
    </div>
  )
}

function HealthTab() {
  const { data: h } = useQuery({ queryKey: ['set-health'], queryFn: () => api.systemHealth(), refetchInterval: 30_000 })
  return (
    <div>
      <div style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '14px 16px', marginBottom: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div><span style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-heading)' }}>LangGraph Dev</span><div style={{ fontSize: 13, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 1 }}>{h?.langgraph_dev?.url ?? '—'}</div></div>
          <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)', color: h?.langgraph_dev?.running ? '#10b981' : '#f43f5e', padding: '2px 7px', borderRadius: 3, background: h?.langgraph_dev?.running ? 'rgba(16,185,129,0.1)' : 'rgba(244,63,94,0.1)' }}>{h?.langgraph_dev?.running ? 'Running' : 'Offline'}</span>
        </div>
      </div>
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
  const { data: stats } = useQuery({ queryKey: ['set-analytics'], queryFn: () => api.systemHealth() })
  return (
    <div>
      <p style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 14, marginBottom: 16 }}>Cross-lab statistics and research analytics.</p>
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <div style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '14px 16px' }}>
            <div style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', marginBottom: 2 }}>LangGraph dev</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: stats.langgraph_dev.running ? '#10b981' : '#f43f5e' }}>{stats.langgraph_dev.running ? 'Online' : 'Offline'}</div>
          </div>
          <div style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '14px 16px' }}>
            <div style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', marginBottom: 2 }}>Skills</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#818cf8' }}>{stats.skills_available}</div>
          </div>
        </div>
      )}
      <p style={{ color: 'var(--text-dim)', fontSize: 13, marginTop: 20 }}>Full analytics available at the <a href="/analytics" style={{ color: '#818cf8' }}>old Analytics page</a>.</p>
    </div>
  )
}

export function SettingsPage() {
  const [tab, setTab] = useState<'models' | 'prompt' | 'cron' | 'mcp' | 'memory' | 'health' | 'analytics'>('models')

  const tabs = [
    { key: 'models', label: 'Models' },
    { key: 'prompt', label: 'Prompt' },
    { key: 'cron', label: 'Schedules' },
    { key: 'mcp', label: 'MCP' },
    { key: 'memory', label: 'Memory' },
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

      {tab === 'models' && <ModelTab />}
      {tab === 'prompt' && <SystemPromptTab />}
      {tab === 'cron' && <CronTab />}
      {tab === 'mcp' && <McpTab />}
      {tab === 'memory' && <MemoryTab />}
      {tab === 'health' && <HealthTab />}
      {tab === 'analytics' && <AnalyticsTab />}
    </div>
  )
}
