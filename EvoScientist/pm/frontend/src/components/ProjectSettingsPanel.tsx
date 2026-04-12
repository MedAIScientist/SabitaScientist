import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Project, Member } from '../api'
import { useAuth } from '../auth'

interface ProjectSettingsPanelProps {
  project: Project
  projectId: string
  onClose: () => void
}

const ROLE_COLORS: Record<string, string> = {
  owner: '#ff8015',
  editor: '#f59e0b',
  viewer: '#64748b',
}

const labelStyle: React.CSSProperties = {
  fontSize: 15,
  color: 'var(--text-dim)',
  fontFamily: 'var(--font-mono)',
  letterSpacing: '0.1em',
  display: 'block',
  marginBottom: 3,
  marginTop: 10,
  textTransform: 'uppercase' as const,
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  background: 'var(--surface-input)',
  border: '1px solid var(--border)',
  borderRadius: 4,
  color: 'var(--text)',
  padding: '5px 8px',
  fontSize: 20,
  fontFamily: 'var(--font-mono)',
  boxSizing: 'border-box' as const,
  outline: 'none',
}

export function ProjectSettingsPanel({ project, projectId, onClose }: ProjectSettingsPanelProps) {
  const { username } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Project details state
  const [editName, setEditName] = useState(project.name)
  const [editDesc, setEditDesc] = useState(project.description ?? '')
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const deleteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Add member state
  const [searchQ, setSearchQ] = useState('')
  const [searchResults, setSearchResults] = useState<{ id: string; username: string }[]>([])
  const [selectedUser, setSelectedUser] = useState<{ id: string; username: string } | null>(null)
  const [addRole, setAddRole] = useState<'owner' | 'editor' | 'viewer'>('editor')
  const [addError, setAddError] = useState<string | null>(null)
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Stable onClose ref to avoid stale closure in Escape handler
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  // Mounted flag to prevent state updates after unmount
  const mountedRef = useRef(true)

  // Cleanup timers on unmount
  useEffect(() => () => {
    mountedRef.current = false
    if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current)
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
  }, [])

  // Sync local state when project prop changes (e.g. after a successful save)
  useEffect(() => {
    setEditName(project.name)
    setEditDesc(project.description ?? '')
  }, [project.name, project.description])

  // Escape key closes panel
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onCloseRef.current()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [])

  // Mutations
  const updateProject = useMutation({
    mutationFn: (data: { name?: string; description?: string | null }) =>
      api.updateProject(projectId, data),
    onSuccess: () => {
      setSaveError(null)
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
    onError: () => setSaveError('Save failed — please retry.'),
  })

  const deleteProject = useMutation({
    mutationFn: () => api.deleteProject(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      navigate('/projects')
    },
    onError: (err: Error) => {
      setDeleteError(err.message || 'Delete failed')
      setDeleteConfirm(false)
    },
  })

  const removeMember = useMutation({
    mutationFn: (userId: string) => api.removeMember(projectId, userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['project', projectId] }),
  })

  const updateMemberRole = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      api.updateMemberRole(projectId, userId, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['project', projectId] }),
  })

  const addMemberMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      api.addMember(projectId, userId, role),
    onSuccess: () => {
      setAddError(null)
      setSearchQ('')
      setSelectedUser(null)
      setSearchResults([])
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
    },
    onError: () => setAddError('Could not add researcher — they may already be a member.'),
  })

  // Handlers
  const handleSave = useCallback(() => {
    setSaveError(null)
    updateProject.mutate({
      name: editName.trim(),
      description: editDesc.trim() || null,
    })
  }, [editName, editDesc, updateProject])

  const handleDeleteClick = useCallback(() => {
    if (!deleteConfirm) {
      setDeleteConfirm(true)
      deleteTimerRef.current = setTimeout(() => setDeleteConfirm(false), 3000)
    } else {
      if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current)
      deleteProject.mutate()
    }
  }, [deleteConfirm, deleteProject])

  const handleSearchChange = useCallback((value: string) => {
    setSearchQ(value)
    setSelectedUser(null)
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    if (value.length >= 1) {
      searchTimerRef.current = setTimeout(async () => {
        try {
          const results = await api.searchUsers(value)
          if (mountedRef.current) setSearchResults(results.slice(0, 5))
        } catch {
          setSearchResults([])
        }
      }, 300)
    } else {
      setSearchResults([])
    }
  }, [])

  const handleSelectUser = useCallback((user: { id: string; username: string }) => {
    setSelectedUser(user)
    setSearchQ(user.username)
    setSearchResults([])
  }, [])

  const handleAddMember = useCallback(() => {
    if (!selectedUser) return
    setAddError(null)
    addMemberMutation.mutate({ userId: selectedUser.id, role: addRole })
  }, [selectedUser, addRole, addMemberMutation])

  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, width: 340, height: '100vh',
      background: 'var(--surface-panel)',
      borderLeft: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column',
      animation: 'slideInRight 0.22s ease',
      zIndex: 50, overflowY: 'auto',
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 16px', borderBottom: '1px solid var(--border-subtle)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        flexShrink: 0,
      }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 700, color: '#ff8015', letterSpacing: '0.08em' }}>
          PROJECT SETTINGS
        </span>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', color: 'var(--text-3)', fontSize: 21, cursor: 'pointer', padding: '2px 6px' }}
        >×</button>
      </div>

      <div style={{ padding: '0 16px 24px', flex: 1 }}>

        {/* Section 1: Project Details */}
        <div style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: 16, marginBottom: 16 }}>
          <div style={{ marginTop: 14, fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', fontWeight: 700 }}>
            PROJECT DETAILS
          </div>

          <label style={labelStyle}>NAME</label>
          <input value={editName} onChange={e => setEditName(e.target.value)} style={inputStyle} />

          <label style={labelStyle}>DESCRIPTION</label>
          <textarea
            value={editDesc}
            onChange={e => setEditDesc(e.target.value)}
            rows={3}
            style={{ ...inputStyle, resize: 'none' }}
          />

          <button
            onClick={handleSave}
            disabled={updateProject.isPending || !editName.trim()}
            style={{
              marginTop: 10, width: '100%',
              background: 'rgba(255,128,21,0.12)',
              border: '1px solid rgba(255,128,21,0.28)',
              borderRadius: 4, padding: '6px 0',
              color: '#ff8015', fontSize: 16, fontWeight: 700,
              fontFamily: 'var(--font-mono)', cursor: 'pointer',
              opacity: updateProject.isPending ? 0.5 : 1,
            }}
          >
            {updateProject.isPending ? 'saving…' : 'SAVE'}
          </button>
          {saveError && (
            <div style={{ marginTop: 5, fontSize: 15, color: '#f43f5e', fontFamily: 'var(--font-mono)' }}>{saveError}</div>
          )}

          <button
            onClick={handleDeleteClick}
            style={{
              marginTop: 8, width: '100%',
              background: deleteConfirm ? 'rgba(244,63,94,0.15)' : 'rgba(244,63,94,0.06)',
              border: `1px solid ${deleteConfirm ? 'rgba(244,63,94,0.45)' : 'rgba(244,63,94,0.2)'}`,
              borderRadius: 4, padding: '5px 0',
              color: '#f43f5e', fontSize: 16, fontWeight: 700,
              fontFamily: 'var(--font-mono)', cursor: 'pointer',
            }}
          >
            {deleteConfirm ? 'CONFIRM DELETE ?' : 'DELETE PROJECT'}
          </button>
          {deleteError && (
            <div style={{ color: '#f43f5e', fontSize: 20, marginTop: 4 }}>{deleteError}</div>
          )}
        </div>

        {/* Section 2: Team Members */}
        <div style={{ fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', fontWeight: 700, marginBottom: 10 }}>
          TEAM MEMBERS · {project.members.length}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 16 }}>
          {project.members.map((m: Member) => {
            const isSelf = !!username && m.username === username
            return (
              <div key={m.user_id} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                background: 'var(--surface-comment)', borderRadius: 5, padding: '7px 10px',
              }}>
                <span style={{ flex: 1, fontSize: 20, color: 'var(--text)', fontFamily: 'var(--font-mono)' }}>
                  {m.username}
                </span>
                <span style={{
                  fontSize: 15, fontWeight: 700,
                  fontFamily: 'var(--font-mono)',
                  color: ROLE_COLORS[m.role] ?? '#64748b',
                  letterSpacing: '0.08em',
                  padding: '1px 4px',
                  border: `1px solid ${ROLE_COLORS[m.role] ?? '#64748b'}40`,
                  borderRadius: 3,
                }}>
                  {m.role.toUpperCase()}
                </span>
                <select
                  value={m.role}
                  disabled={isSelf}
                  onChange={e => updateMemberRole.mutate({ userId: m.user_id, role: e.target.value })}
                  style={{
                    background: 'var(--surface-input)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 3,
                    color: ROLE_COLORS[m.role] ?? '#64748b',
                    fontSize: 15, fontWeight: 700,
                    fontFamily: 'var(--font-mono)',
                    cursor: isSelf ? 'not-allowed' : 'pointer',
                    padding: '2px 4px',
                    opacity: isSelf ? 0.5 : 1,
                  }}
                >
                  <option value="owner">OWNER</option>
                  <option value="editor">EDITOR</option>
                  <option value="viewer">VIEWER</option>
                </select>
                <button
                  disabled={isSelf}
                  onClick={() => removeMember.mutate(m.user_id)}
                  style={{
                    background: 'none',
                    border: '1px solid rgba(244,63,94,0.2)',
                    borderRadius: 3, color: '#f43f5e',
                    fontSize: 16, cursor: isSelf ? 'not-allowed' : 'pointer',
                    padding: '1px 5px',
                    opacity: isSelf ? 0.3 : 1,
                  }}
                >✕</button>
              </div>
            )
          })}
        </div>

        {/* Add Researcher */}
        <div style={{ fontSize: 16, color: '#3d4e64', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', fontWeight: 700, marginBottom: 8 }}>
          ADD RESEARCHER
        </div>

        <div style={{ position: 'relative' }}>
          <input
            value={searchQ}
            onChange={e => handleSearchChange(e.target.value)}
            placeholder="Search by username…"
            style={inputStyle}
          />
          {searchResults.length > 0 && (
            <div style={{
              position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100,
              background: 'var(--surface-panel)',
              border: '1px solid rgba(255,128,21,0.2)',
              borderRadius: 4,
              boxShadow: '0 8px 20px rgba(0,0,0,0.4)',
            }}>
              {searchResults.map(u => (
                <div
                  key={u.id}
                  onClick={() => handleSelectUser(u)}
                  style={{
                    padding: '7px 10px',
                    fontSize: 20, color: 'var(--text)',
                    fontFamily: 'var(--font-mono)',
                    cursor: 'pointer',
                    borderBottom: '1px solid var(--border-subtle)',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.07)' }}
                  onMouseLeave={e => { e.currentTarget.style.background = '' }}
                >
                  {u.username}
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
          <select
            value={addRole}
            onChange={e => setAddRole(e.target.value as typeof addRole)}
            style={{ ...inputStyle, cursor: 'pointer', flex: 1 }}
          >
            <option value="owner">OWNER</option>
            <option value="editor">EDITOR</option>
            <option value="viewer">VIEWER</option>
          </select>
          <button
            onClick={handleAddMember}
            disabled={!selectedUser || addMemberMutation.isPending}
            style={{
              background: 'rgba(255,128,21,0.1)',
              border: '1px solid rgba(255,128,21,0.25)',
              borderRadius: 4, color: '#ff8015',
              fontSize: 16, fontWeight: 700,
              fontFamily: 'var(--font-mono)',
              padding: '5px 12px',
              cursor: selectedUser ? 'pointer' : 'not-allowed',
              opacity: !selectedUser || addMemberMutation.isPending ? 0.5 : 1,
            }}
          >
            {addMemberMutation.isPending ? '…' : 'ADD'}
          </button>
        </div>
        {addError && (
          <div style={{ marginTop: 5, fontSize: 15, color: '#f43f5e', fontFamily: 'var(--font-mono)' }}>{addError}</div>
        )}
      </div>
    </div>
  )
}
