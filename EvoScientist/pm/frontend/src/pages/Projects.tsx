import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Project } from '../api'
import { useAuth } from '../auth'

const ACCENT_CYCLE = ['#22d3ee', '#f59e0b', '#10b981', '#8b5cf6', '#ec4899', '#f43f5e']

export function Projects() {
  const { username, logout } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)

  const { data: projects = [], isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: api.listProjects,
    refetchInterval: 30_000,
  })

  const createMutation = useMutation({
    mutationFn: (name: string) => api.createProject(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setNewName('')
      setCreating(false)
    },
  })

  if (isLoading) return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100vh', color: '#334155',
      fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.08em',
    }}>
      LOADING…
    </div>
  )

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>

      {/* ── Header ── */}
      <div style={{
        padding: '0 28px', height: 54,
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'rgba(13,21,38,0.85)', backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: '#22d3ee', boxShadow: '0 0 7px #22d3ee',
          }} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600, letterSpacing: '0.04em', color: '#f1f5f9' }}>
            EvoScientist
          </span>
          <span style={{ color: '#334155', fontSize: 11, fontFamily: 'var(--font-mono)' }}>/</span>
          <span style={{ color: '#22d3ee', fontSize: 12, fontFamily: 'var(--font-mono)' }}>projects</span>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span style={{ color: '#3d4e64', fontSize: 11, fontFamily: 'var(--font-mono)' }}>{username}</span>
          <button
            onClick={logout}
            style={{
              cursor: 'pointer',
              background: 'rgba(244,63,94,0.07)',
              border: '1px solid rgba(244,63,94,0.18)',
              borderRadius: 5, color: '#f43f5e',
              padding: '3px 11px', fontSize: 9, fontWeight: 700,
              letterSpacing: '0.1em', transition: 'background 0.14s',
              fontFamily: 'var(--font-mono)',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(244,63,94,0.14)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(244,63,94,0.07)' }}
          >LOGOUT</button>
        </div>
      </div>

      {/* ── Content ── */}
      <div style={{ maxWidth: 700, margin: '0 auto', padding: '40px 28px' }}>
        <div style={{ marginBottom: 28 }}>
          <h1 style={{ margin: '0 0 5px', fontSize: 22, fontWeight: 600, fontFamily: 'var(--font-mono)', color: '#f1f5f9' }}>
            Research Projects
          </h1>
          <p style={{ margin: 0, fontSize: 10, color: '#3d4e64', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
            {projects.length} PROJECT{projects.length !== 1 ? 'S' : ''} · SYNCS EVERY 30S
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 9, marginBottom: 24 }}>
          {projects.map((p: Project, i: number) => {
            const accent = ACCENT_CYCLE[i % ACCENT_CYCLE.length]
            return (
              <div
                key={p.id}
                onClick={() => navigate(`/projects/${p.id}`)}
                style={{
                  padding: '15px 18px',
                  background: 'rgba(13,21,38,0.6)',
                  border: '1px solid rgba(100,140,200,0.09)',
                  borderLeft: `3px solid ${accent}`,
                  borderRadius: '0 8px 8px 0',
                  cursor: 'pointer',
                  transition: 'background 0.14s, transform 0.14s, box-shadow 0.14s',
                  animation: 'fadeInUp 0.22s ease both',
                  animationDelay: `${i * 0.04}s`,
                  display: 'flex', alignItems: 'center', gap: 14,
                }}
                onMouseEnter={e => {
                  const el = e.currentTarget
                  el.style.background = 'rgba(17,30,53,0.85)'
                  el.style.transform = 'translateX(4px)'
                  el.style.boxShadow = `0 4px 18px rgba(0,0,0,0.28), -2px 0 0 ${accent}`
                }}
                onMouseLeave={e => {
                  const el = e.currentTarget
                  el.style.background = 'rgba(13,21,38,0.6)'
                  el.style.transform = ''
                  el.style.boxShadow = ''
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <strong style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', display: 'block' }}>{p.name}</strong>
                  {p.description && (
                    <p style={{ margin: '3px 0 0', color: '#3d4e64', fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {p.description}
                    </p>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                  <span style={{ fontSize: 9, color: '#3d4e64', fontFamily: 'var(--font-mono)' }}>
                    {p.members.length} MEMBER{p.members.length !== 1 ? 'S' : ''}
                  </span>
                  <span style={{ color: '#334155', fontSize: 13 }}>→</span>
                </div>
              </div>
            )
          })}
          {projects.length === 0 && (
            <p style={{ color: '#334155', fontSize: 12, padding: '10px 0', fontStyle: 'italic' }}>
              No projects yet. Create your first one below.
            </p>
          )}
        </div>

        {creating ? (
          <form
            onSubmit={e => { e.preventDefault(); createMutation.mutate(newName) }}
            style={{
              display: 'flex', gap: 8, padding: 14,
              background: 'rgba(13,21,38,0.65)',
              border: '1px solid rgba(34,211,238,0.18)',
              borderRadius: 8, animation: 'fadeInUp 0.18s ease',
            }}
          >
            <input
              autoFocus value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder="Project name…" required
              style={{
                flex: 1, padding: '8px 11px',
                background: 'rgba(7,11,18,0.65)',
                border: '1px solid rgba(34,211,238,0.2)',
                borderRadius: 6, color: '#e2e8f0', fontSize: 13, outline: 'none',
              }}
            />
            <button type="submit" disabled={createMutation.isPending} style={{
              padding: '8px 16px', cursor: 'pointer',
              background: '#22d3ee', color: '#070b12',
              border: 'none', borderRadius: 6, fontSize: 10, fontWeight: 700,
              letterSpacing: '0.06em', fontFamily: 'var(--font-mono)',
            }}>CREATE</button>
            <button type="button" onClick={() => setCreating(false)} style={{
              padding: '8px 12px', cursor: 'pointer',
              background: 'rgba(100,140,200,0.07)',
              border: '1px solid rgba(100,140,200,0.13)',
              borderRadius: 6, color: '#475569', fontSize: 12,
            }}>✕</button>
          </form>
        ) : (
          <button
            onClick={() => setCreating(true)}
            style={{
              padding: '9px 18px', cursor: 'pointer',
              background: 'rgba(34,211,238,0.07)',
              border: '1px solid rgba(34,211,238,0.18)',
              borderRadius: 7, color: '#22d3ee',
              fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
              transition: 'background 0.14s',
              fontFamily: 'var(--font-mono)',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(34,211,238,0.13)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(34,211,238,0.07)' }}
          >+ NEW PROJECT</button>
        )}
      </div>
    </div>
  )
}
