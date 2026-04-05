import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Project } from '../api'
import { useAuth } from '../auth'

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

  if (isLoading) return <p style={{ padding: 24 }}>Loading\u2026</p>

  return (
    <div style={{ padding: 24, fontFamily: 'system-ui', maxWidth: 800, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ margin: 0 }}>Projects</h1>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span style={{ color: '#666' }}>{username}</span>
          <button onClick={logout} style={{ cursor: 'pointer' }}>Log out</button>
        </div>
      </div>

      <div style={{ display: 'grid', gap: 12, marginBottom: 24 }}>
        {projects.map((p: Project) => (
          <div
            key={p.id}
            onClick={() => navigate(`/projects/${p.id}`)}
            style={{ padding: 16, border: '1px solid #ddd', borderRadius: 8, cursor: 'pointer' }}
          >
            <strong>{p.name}</strong>
            {p.description && <p style={{ margin: '4px 0 0', color: '#666', fontSize: 14 }}>{p.description}</p>}
            <p style={{ margin: '4px 0 0', fontSize: 12, color: '#999' }}>
              {p.members.length} member{p.members.length !== 1 ? 's' : ''}
            </p>
          </div>
        ))}
        {projects.length === 0 && <p style={{ color: '#666' }}>No projects yet.</p>}
      </div>

      {creating ? (
        <form onSubmit={e => { e.preventDefault(); createMutation.mutate(newName) }} style={{ display: 'flex', gap: 8 }}>
          <input
            autoFocus value={newName} onChange={e => setNewName(e.target.value)}
            placeholder="Project name" required style={{ flex: 1, padding: 8 }}
          />
          <button type="submit" disabled={createMutation.isPending}>Create</button>
          <button type="button" onClick={() => setCreating(false)}>Cancel</button>
        </form>
      ) : (
        <button onClick={() => setCreating(true)} style={{ padding: '8px 16px', cursor: 'pointer' }}>
          + New Project
        </button>
      )}
    </div>
  )
}
