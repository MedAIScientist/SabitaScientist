// EvoScientist/pm/frontend/src/components/task/TaskEditForm.tsx
import React from 'react'
import { DeadlinePicker } from '../DeadlinePicker'
import { inputStyle, selectStyle, labelStyle } from './taskStyles'
import type { Task, Member } from '../../api'

interface Props {
  editTitle: string;        setEditTitle: (v: string) => void
  editStatus: Task['status']; setEditStatus: (v: Task['status']) => void
  editPriority: Task['priority']; setEditPriority: (v: Task['priority']) => void
  editDeadline: string;     setEditDeadline: (v: string) => void
  editDescription: string;  setEditDescription: (v: string) => void
  editAssigneeId: string;   setEditAssigneeId: (v: string) => void
  onSave: () => void
  onDeleteClick: () => void
  isSaving: boolean
  isDeleting: boolean
  deleteConfirm: boolean
  members: Member[]
}

export function TaskEditForm({
  editTitle, setEditTitle,
  editStatus, setEditStatus,
  editPriority, setEditPriority,
  editDeadline, setEditDeadline,
  editDescription, setEditDescription,
  editAssigneeId, setEditAssigneeId,
  onSave, onDeleteClick,
  isSaving, isDeleting, deleteConfirm,
  members,
}: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <label style={labelStyle}>Experiment Title</label>
        <input
          value={editTitle}
          onChange={e => setEditTitle(e.target.value)}
          style={inputStyle}
          onFocus={e => { e.currentTarget.style.borderColor = 'rgba(255,128,21,0.3)' }}
          onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
        />
      </div>

      <div>
        <label style={labelStyle}>Protocol Status</label>
        <select
          value={editStatus}
          onChange={e => setEditStatus(e.target.value as Task['status'])}
          style={selectStyle}
        >
          <option value="todo">PLANNED</option>
          <option value="in_progress">IN PROGRESS</option>
          <option value="done">COMPLETE</option>
        </select>
      </div>

      <div>
        <label style={labelStyle}>Priority Level</label>
        <select
          value={editPriority}
          onChange={e => setEditPriority(e.target.value as Task['priority'])}
          style={selectStyle}
        >
          <option value="high">CRITICAL</option>
          <option value="medium">STANDARD</option>
          <option value="low">ROUTINE</option>
        </select>
      </div>

      <div>
        <label style={labelStyle}>Deadline</label>
        <DeadlinePicker
          value={editDeadline}
          onChange={setEditDeadline}
          inputStyle={inputStyle}
        />
      </div>

      <div>
        <label style={labelStyle}>Experiment Notes</label>
        <textarea
          value={editDescription}
          onChange={e => setEditDescription(e.target.value)}
          rows={4}
          style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.55 }}
          onFocus={e => { e.currentTarget.style.borderColor = 'rgba(255,128,21,0.3)' }}
          onBlur={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
        />
      </div>

      <div>
        <label style={labelStyle}>Assigned Researcher</label>
        <select
          value={editAssigneeId}
          onChange={e => setEditAssigneeId(e.target.value)}
          style={selectStyle}
        >
          <option value="">Unassigned</option>
          {members.map(m => (
            <option key={m.user_id} value={m.user_id}>{m.username}</option>
          ))}
        </select>
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <button
          onClick={onSave}
          disabled={isSaving}
          style={{
            flex: 1, padding: '9px 0', fontSize: 20, cursor: 'pointer',
            background: 'rgba(255,128,21,0.1)',
            border: '1px solid rgba(255,128,21,0.28)',
            borderRadius: 7, color: '#ff8015', fontWeight: 700,
            letterSpacing: '0.08em', fontFamily: 'var(--font-mono)',
            transition: 'background 0.14s',
            opacity: isSaving ? 0.6 : 1,
          }}
          onMouseEnter={e => { if (!isSaving) e.currentTarget.style.background = 'rgba(255,128,21,0.2)' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.1)' }}
        >{isSaving ? 'saving…' : 'SAVE'}</button>
      </div>

      <button
        onClick={onDeleteClick}
        disabled={isDeleting}
        style={{
          width: '100%', padding: '8px 0', fontSize: 20, cursor: 'pointer',
          background: deleteConfirm ? 'rgba(244,63,94,0.15)' : 'rgba(244,63,94,0.07)',
          border: `1px solid ${deleteConfirm ? 'rgba(244,63,94,0.4)' : 'rgba(244,63,94,0.2)'}`,
          borderRadius: 7, color: '#f43f5e', fontWeight: 700,
          letterSpacing: '0.08em', fontFamily: 'var(--font-mono)',
          transition: 'all 0.18s',
        }}
      >{deleteConfirm ? 'CONFIRM DELETE ?' : 'DELETE'}</button>
    </div>
  )
}
