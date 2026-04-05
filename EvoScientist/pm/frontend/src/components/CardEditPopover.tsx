import React, { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Task } from '../api'

interface CardEditPopoverProps {
  task: Task
  projectId: string
  anchorRect: DOMRect
  onClose: () => void
}

export function CardEditPopover({ task, projectId, anchorRect, onClose }: CardEditPopoverProps) {
  const queryClient = useQueryClient()
  const panelRef = useRef<HTMLDivElement>(null)

  const [title, setTitle] = useState(task.title)
  const [priority, setPriority] = useState<Task['priority']>(task.priority)
  const [deadline, setDeadline] = useState(task.deadline ?? '')

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
      onClose()
    },
  })

  // Click-outside handler
  useEffect(() => {
    function handleMouseDown(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [onClose])

  function handleKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'Escape') {
      onClose()
    }
  }

  function handleSave() {
    updateMutation.mutate({
      title,
      priority,
      deadline: deadline || undefined,
    })
  }

  const labelStyle: React.CSSProperties = {
    fontSize: 9,
    color: '#3d4e64',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.1em',
    display: 'block',
    marginBottom: 3,
    marginTop: 8,
  }

  const fieldStyle: React.CSSProperties = {
    width: '100%',
    background: '#070b12',
    border: '1px solid rgba(100,140,200,0.18)',
    color: '#f1f5f9',
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
        background: '#0d1526',
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
      <input
        type="date"
        value={deadline}
        onChange={e => setDeadline(e.target.value)}
        style={fieldStyle}
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
    </div>
  )
}
