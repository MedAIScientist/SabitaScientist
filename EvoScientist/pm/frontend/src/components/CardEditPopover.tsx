import React, { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Task } from '../api'
import { DeadlinePicker } from './DeadlinePicker'

interface CardEditPopoverProps {
  task: Task
  projectId: string
  anchorRect: DOMRect
  onClose: () => void
}

export function CardEditPopover({ task, projectId, anchorRect, onClose }: CardEditPopoverProps) {
  const queryClient = useQueryClient()
  const panelRef = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose  // always up to date, no re-render

  const [title, setTitle] = useState(task.title)
  const [priority, setPriority] = useState<Task['priority']>(task.priority)
  const [deadline, setDeadline] = useState(task.deadline ?? '')
  const [saveError, setSaveError] = useState<string | null>(null)

  // Position: right of card with 8px gap, flip left if no room
  const width = 240
  const gap = 8
  const left =
    anchorRect.right + width + gap > window.innerWidth
      ? anchorRect.left - width - gap
      : anchorRect.right + gap

  const updateMutation = useMutation({
    mutationFn: (data: Partial<Task>) => api.updateTask(projectId, task.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      onCloseRef.current()
    },
    onError: () => setSaveError('Save failed — please retry.'),
  })

  // Click-outside handler — stable, no re-attachment on onClose change
  useEffect(() => {
    function handleMouseDown(e: MouseEvent) {
      if (panelRef.current && e.target instanceof Node && !panelRef.current.contains(e.target)) {
        onCloseRef.current()
      }
    }
    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [])

  // Close on scroll or resize (popover position becomes stale)
  useEffect(() => {
    const close = () => onCloseRef.current()
    window.addEventListener('scroll', close, true)
    window.addEventListener('resize', close)
    return () => {
      window.removeEventListener('scroll', close, true)
      window.removeEventListener('resize', close)
    }
  }, [])

  function handleKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'Escape') {
      onCloseRef.current()
    }
  }

  function handleSave() {
    setSaveError(null)
    updateMutation.mutate({
      title,
      priority,
      deadline: deadline || undefined,
    })
  }

  const labelStyle: React.CSSProperties = {
    fontSize: 9,
    color: 'var(--text-dim)',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.1em',
    display: 'block',
    marginBottom: 3,
    marginTop: 8,
  }

  const fieldStyle: React.CSSProperties = {
    width: '100%',
    background: 'var(--surface-input)',
    border: '1px solid var(--border)',
    color: 'var(--text)',
    borderRadius: 4,
    padding: '4px 8px',
    fontSize: 11,
    fontFamily: 'var(--font-mono)',
    boxSizing: 'border-box',
  }

  return (
    <div
      role="dialog"
      ref={panelRef}
      onKeyDown={handleKeyDown}
      style={{
        position: 'fixed',
        top: anchorRect.top,
        left,
        width,
        background: 'var(--surface-panel)',
        border: '1px solid rgba(34,211,238,0.25)',
        borderRadius: 6,
        padding: 12,
        boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
        zIndex: 1000,
      }}
    >
      <label style={labelStyle}>EXPERIMENT TITLE</label>
      <input
        autoFocus
        value={title}
        onChange={e => setTitle(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') handleSave() }}
        style={fieldStyle}
      />

      <label style={labelStyle}>PRIORITY</label>
      <select
        value={priority}
        onChange={e => setPriority(e.target.value as Task['priority'])}
        style={fieldStyle}
      >
        <option value="high">CRITICAL</option>
        <option value="medium">STANDARD</option>
        <option value="low">ROUTINE</option>
      </select>

      <label style={labelStyle}>DEADLINE</label>
      <DeadlinePicker
        value={deadline}
        onChange={setDeadline}
        inputStyle={fieldStyle}
      />

      <button
        onClick={handleSave}
        disabled={updateMutation.isPending}
        style={{
          marginTop: 10,
          width: '100%',
          background: 'rgba(34,211,238,0.12)',
          border: '1px solid rgba(34,211,238,0.28)',
          color: '#22d3ee',
          borderRadius: 4,
          padding: '5px 0',
          fontSize: 10,
          fontWeight: 700,
          fontFamily: 'var(--font-mono)',
          cursor: 'pointer',
          opacity: updateMutation.isPending ? 0.5 : 1,
        }}
      >
        {updateMutation.isPending ? 'saving…' : 'SAVE'}
      </button>
      {saveError && (
        <div style={{ marginTop: 6, fontSize: 9, color: '#f43f5e', fontFamily: 'var(--font-mono)' }}>
          {saveError}
        </div>
      )}
    </div>
  )
}
