import React, { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listPhases,
  createPhase,
  updatePhase,
  deletePhase,
  ProjectPhase,
} from '../api'

interface PhaseManagerProps {
  projectId: string
  token: string
}

const PRESET_COLORS = ['#6366f1', '#ec4899', '#f59e0b', '#10b981', '#3b82f6', '#ef4444']

const sectionLabelStyle: React.CSSProperties = {
  fontSize: 16,
  color: 'var(--text-dim)',
  fontFamily: 'var(--font-mono)',
  letterSpacing: '0.1em',
  fontWeight: 700,
  marginBottom: 10,
}

const inputStyle: React.CSSProperties = {
  background: 'var(--surface-input)',
  border: '1px solid var(--border)',
  borderRadius: 4,
  color: 'var(--text)',
  padding: '4px 7px',
  fontSize: 15,
  fontFamily: 'var(--font-mono)',
  boxSizing: 'border-box' as const,
  outline: 'none',
}

function ColorPicker({
  value,
  onChange,
}: {
  value: string
  onChange: (c: string) => void
}) {
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
      {PRESET_COLORS.map(c => (
        <button
          key={c}
          title={c}
          onClick={() => onChange(c)}
          style={{
            width: 16,
            height: 16,
            borderRadius: '50%',
            background: c,
            border: value === c ? '2px solid var(--text)' : '2px solid transparent',
            cursor: 'pointer',
            padding: 0,
            flexShrink: 0,
          }}
        />
      ))}
    </div>
  )
}

function PhaseRow({
  phase,
  projectId,
  token,
}: {
  phase: ProjectPhase
  projectId: string
  token: string
}) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState(phase.name)
  const [editColor, setEditColor] = useState(phase.color)
  const [editDate, setEditDate] = useState(phase.target_date ?? '')
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const deleteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => () => {
    if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current)
  }, [])

  const updateMutation = useMutation({
    mutationFn: (data: Partial<{ name: string; color: string; target_date: string | null }>) =>
      updatePhase(projectId, phase.id, data, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['phases', projectId] })
      setEditing(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deletePhase(projectId, phase.id, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['phases', projectId] })
    },
    onError: (err: Error) => {
      setDeleteError(err.message ?? 'Delete failed')
    },
  })

  function handleSaveEdit() {
    updateMutation.mutate({
      name: editName.trim(),
      color: editColor,
      target_date: editDate || null,
    })
  }

  function handleDeleteClick() {
    if (!deleteConfirm) {
      setDeleteConfirm(true)
      deleteTimerRef.current = setTimeout(() => setDeleteConfirm(false), 3000)
    } else {
      if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current)
      deleteMutation.mutate()
    }
  }

  if (editing) {
    return (
      <div style={{
        background: 'var(--surface-comment)',
        borderRadius: 5,
        padding: '8px 10px',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
      }}>
        <input
          value={editName}
          onChange={e => setEditName(e.target.value)}
          style={{ ...inputStyle, width: '100%' }}
          autoFocus
        />
        <ColorPicker value={editColor} onChange={setEditColor} />
        <input
          type="date"
          value={editDate}
          onChange={e => setEditDate(e.target.value)}
          style={{ ...inputStyle, width: '100%' }}
        />
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            onClick={handleSaveEdit}
            disabled={updateMutation.isPending || !editName.trim()}
            style={{
              flex: 1,
              background: 'rgba(255,128,21,0.12)',
              border: '1px solid rgba(255,128,21,0.28)',
              borderRadius: 4, padding: '4px 0',
              color: '#ff8015', fontSize: 14, fontWeight: 700,
              fontFamily: 'var(--font-mono)', cursor: 'pointer',
              opacity: updateMutation.isPending || !editName.trim() ? 0.5 : 1,
            }}
          >
            {updateMutation.isPending ? '…' : 'SAVE'}
          </button>
          <button
            onClick={() => setEditing(false)}
            style={{
              background: 'none',
              border: '1px solid var(--border)',
              borderRadius: 4, padding: '4px 8px',
              color: 'var(--text-dim)', fontSize: 14,
              fontFamily: 'var(--font-mono)', cursor: 'pointer',
            }}
          >
            CANCEL
          </button>
        </div>
        {updateMutation.isError && (
          <div style={{ fontSize: 14, color: '#f43f5e', fontFamily: 'var(--font-mono)' }}>
            {updateMutation.error instanceof Error ? updateMutation.error.message : 'Update failed'}
          </div>
        )}
      </div>
    )
  }

  return (
    <>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        background: 'var(--surface-comment)', borderRadius: 5, padding: '6px 10px',
      }}>
        {/* Color swatch */}
        <div style={{
          width: 12, height: 12, borderRadius: '50%',
          background: phase.color, flexShrink: 0,
        }} />

        {/* Phase name + optional date */}
        <span style={{ flex: 1, fontSize: 15, color: 'var(--text)', fontFamily: 'var(--font-mono)', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {phase.name}
          {phase.target_date && (
            <span style={{ marginLeft: 6, fontSize: 13, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
              {phase.target_date}
            </span>
          )}
        </span>

        {/* Edit button */}
        <button
          onClick={() => { setEditing(true); setEditName(phase.name); setEditColor(phase.color); setEditDate(phase.target_date ?? '') }}
          title="Edit phase"
          style={{
            background: 'none', border: 'none',
            color: 'var(--text-3)', fontSize: 14,
            cursor: 'pointer', padding: '1px 4px', lineHeight: 1,
          }}
        >✎</button>

        {/* Delete button */}
        <button
          onClick={handleDeleteClick}
          disabled={deleteMutation.isPending}
          title={deleteConfirm ? 'Click again to confirm' : 'Delete phase'}
          style={{
            background: 'none',
            border: deleteConfirm ? '1px solid rgba(244,63,94,0.45)' : 'none',
            borderRadius: 3,
            color: '#f43f5e', fontSize: 14,
            cursor: 'pointer', padding: '1px 4px', lineHeight: 1,
            opacity: deleteMutation.isPending ? 0.5 : 1,
          }}
        >🗑</button>
      </div>
      {deleteError && (
        <div style={{ fontSize: 13, color: '#f43f5e', fontFamily: 'var(--font-mono)', marginTop: 2, paddingLeft: 10 }}>
          {deleteError}
        </div>
      )}
    </>
  )
}

export function PhaseManager({ projectId, token }: PhaseManagerProps) {
  const queryClient = useQueryClient()

  const { data: phases = [], isLoading, isError } = useQuery({
    queryKey: ['phases', projectId],
    queryFn: () => listPhases(projectId, token),
    enabled: !!token,
  })

  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState(PRESET_COLORS[0])
  const [newDate, setNewDate] = useState('')
  const [createError, setCreateError] = useState<string | null>(null)

  const createMutation = useMutation({
    mutationFn: () =>
      createPhase(
        projectId,
        {
          name: newName.trim(),
          color: newColor,
          position: phases.length,
          target_date: newDate || null,
        },
        token,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['phases', projectId] })
      setNewName('')
      setNewColor(PRESET_COLORS[0])
      setNewDate('')
      setCreateError(null)
    },
    onError: (err: Error) => setCreateError(err.message),
  })

  const sortedPhases = [...phases].sort((a, b) => a.position - b.position)

  return (
    <div style={{ marginTop: 4 }}>
      {/* Phase list */}
      {isLoading && (
        <div style={{ fontSize: 14, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', marginBottom: 8 }}>
          loading…
        </div>
      )}
      {isError && (
        <div style={{ fontSize: 14, color: '#f43f5e', fontFamily: 'var(--font-mono)', marginBottom: 8 }}>
          Failed to load phases.
        </div>
      )}
      {!isLoading && sortedPhases.length === 0 && (
        <div style={{ fontSize: 14, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', marginBottom: 8 }}>
          No phases yet.
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 12 }}>
        {sortedPhases.map(phase => (
          <PhaseRow
            key={phase.id}
            phase={phase}
            projectId={projectId}
            token={token}
          />
        ))}
      </div>

      {/* Add Phase form */}
      <div style={{
        background: 'var(--surface-comment)',
        borderRadius: 5,
        padding: '8px 10px',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
      }}>
        <div style={{ fontSize: 13, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontWeight: 700, letterSpacing: '0.08em' }}>
          + ADD PHASE
        </div>
        <input
          value={newName}
          onChange={e => setNewName(e.target.value)}
          placeholder="Phase name…"
          style={{ ...inputStyle, width: '100%' }}
          onKeyDown={e => { if (e.key === 'Enter' && newName.trim()) createMutation.mutate() }}
        />
        <ColorPicker value={newColor} onChange={setNewColor} />
        <input
          type="date"
          value={newDate}
          onChange={e => setNewDate(e.target.value)}
          style={{ ...inputStyle, width: '100%' }}
        />
        <button
          onClick={() => createMutation.mutate()}
          disabled={!newName.trim() || createMutation.isPending}
          style={{
            background: 'rgba(255,128,21,0.12)',
            border: '1px solid rgba(255,128,21,0.28)',
            borderRadius: 4, padding: '5px 0',
            color: '#ff8015', fontSize: 14, fontWeight: 700,
            fontFamily: 'var(--font-mono)', cursor: 'pointer',
            opacity: !newName.trim() || createMutation.isPending ? 0.5 : 1,
          }}
        >
          {createMutation.isPending ? 'saving…' : 'SAVE'}
        </button>
        {createError && (
          <div style={{ fontSize: 14, color: '#f43f5e', fontFamily: 'var(--font-mono)' }}>
            {createError}
          </div>
        )}
      </div>
    </div>
  )
}
