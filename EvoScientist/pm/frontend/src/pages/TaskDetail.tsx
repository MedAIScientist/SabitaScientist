// EvoScientist/pm/frontend/src/pages/TaskDetail.tsx
import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Task, Member } from '../api'
import { AiRunsTab } from '../components/AiRunsTab'
import { TaskDetailView } from '../components/task/TaskDetailView'
import { LabNotesTab } from '../components/task/LabNotesTab'
import { TaskEditForm } from '../components/task/TaskEditForm'
import { useAuth } from '../auth'

interface Props {
  task: Task
  projectId: string
  onClose: () => void
  members: Member[]
}

type Tab = 'details' | 'notes' | 'ai' | 'edit'

export function TaskDetail({ task, projectId, onClose, members }: Props) {
  const queryClient = useQueryClient()
  const { token } = useAuth()

  // ── Active tab ──────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<Tab>('details')

  // ── Queries ─────────────────────────────────────────────────────────────────
  const { data: allTasksData = [] } = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => api.listTasks(projectId),
  })
  const allTasks = allTasksData.map((t: Task) => ({ id: t.id, title: t.title }))

  const { data: comments = [] } = useQuery({
    queryKey: ['comments', task.id],
    queryFn: () => api.listComments(projectId, task.id),
  })

  // ── Edit field state (kept in sync with task prop) ──────────────────────────
  const [editTitle,       setEditTitle]       = useState(task.title)
  const [editStatus,      setEditStatus]      = useState<Task['status']>(task.status)
  const [editPriority,    setEditPriority]    = useState<Task['priority']>(task.priority)
  const [editDeadline,    setEditDeadline]    = useState(task.deadline ?? '')
  const [editDescription, setEditDescription] = useState(task.description ?? '')
  const [editAssigneeId,  setEditAssigneeId]  = useState(task.assignee_id ?? '')

  useEffect(() => {
    setEditTitle(task.title)
    setEditStatus(task.status)
    setEditPriority(task.priority)
    setEditDeadline(task.deadline ?? '')
    setEditDescription(task.description ?? '')
    setEditAssigneeId(task.assignee_id ?? '')
  }, [task])

  // ── Comment state ───────────────────────────────────────────────────────────
  const [commentBody, setCommentBody] = useState('')

  // ── Delete confirmation ─────────────────────────────────────────────────────
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const deleteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Copy state ──────────────────────────────────────────────────────────────
  const [copied, setCopied] = useState(false)
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current)
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
    }
  }, [])

  // ── Mutations ───────────────────────────────────────────────────────────────
  const addComment = useMutation({
    mutationFn: (body: string) => api.addComment(projectId, task.id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comments', task.id] })
      setCommentBody('')
    },
  })

  const updateTask = useMutation({
    mutationFn: (data: Partial<Task>) => api.updateTask(projectId, task.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      setActiveTab('details')
    },
  })

  const deleteTask = useMutation({
    mutationFn: () => api.deleteTask(projectId, task.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      onClose()
    },
  })

  // ── Handlers ────────────────────────────────────────────────────────────────
  async function handleCopySessionId() {
    if (!task.session_id) return
    try {
      await navigator.clipboard.writeText(task.session_id)
      setCopied(true)
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
      copyTimerRef.current = setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard unavailable in non-https context
    }
  }

  function handleSave() {
    updateTask.mutate({
      title: editTitle,
      status: editStatus,
      priority: editPriority,
      deadline: editDeadline || null,
      description: editDescription || null,
      assignee_id: editAssigneeId || null,
    })
  }

  function handleDeleteClick() {
    if (!deleteConfirm) {
      setDeleteConfirm(true)
      deleteTimerRef.current = setTimeout(() => setDeleteConfirm(false), 3000)
    } else {
      if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current)
      deleteTask.mutate()
    }
  }

  // ── Tab bar helper ───────────────────────────────────────────────────────────
  function tabBtn(id: Tab, label: string) {
    const active = activeTab === id
    return (
      <button
        onClick={() => setActiveTab(id)}
        style={{
          padding: '4px 10px', fontSize: 15, fontFamily: 'var(--font-mono)',
          color: active ? '#ff8015' : 'var(--text-3)',
          background: 'none', border: 'none', borderBottomStyle: 'solid',
          borderBottomWidth: 2, borderBottomColor: active ? '#ff8015' : 'transparent',
          cursor: 'pointer', fontWeight: active ? 700 : 400,
        }}
      >{label}</button>
    )
  }

  // ── BLOCKED badge ────────────────────────────────────────────────────────────
  const isBlocked = task.blocked_by && task.blocked_by.length > 0

  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'var(--overlay-bg)',
        backdropFilter: 'blur(4px)',
        display: 'flex', justifyContent: 'flex-end',
        zIndex: 100,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--surface)',
          borderLeft: '1px solid var(--border)',
          boxShadow: '-6px 0 24px rgba(0,0,0,0.12)',
          width: 476, height: '100%', overflowY: 'auto',
          padding: '28px 28px 32px',
          animation: 'slideInRight 0.2s ease',
          display: 'flex', flexDirection: 'column', gap: 20,
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Title row */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          <h2 style={{
            flex: 1, margin: 0, fontSize: 24, fontWeight: 600,
            color: 'var(--text-heading)', lineHeight: 1.35,
            display: 'flex', alignItems: 'flex-start', gap: 8, flexWrap: 'wrap',
          }}>
            <span>{task.title}</span>
            {isBlocked && (
              <span style={{
                fontSize: 13, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
                background: 'rgba(244,63,94,0.1)', border: '1px solid rgba(244,63,94,0.28)',
                color: '#f43f5e', fontFamily: 'var(--font-mono)',
                letterSpacing: '0.08em', whiteSpace: 'nowrap', alignSelf: 'center',
              }}>BLOCKED</span>
            )}
          </h2>
          <button
            onClick={onClose}
            style={{
              flexShrink: 0, cursor: 'pointer',
              background: 'var(--border-subtle)', border: '1px solid var(--border)',
              borderRadius: 6, color: 'var(--text-3)',
              width: 28, height: 28, fontSize: 21, lineHeight: 1,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'color 0.14s, border-color 0.14s',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = '#f43f5e'; e.currentTarget.style.borderColor = 'rgba(244,63,94,0.28)' }}
            onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-3)'; e.currentTarget.style.borderColor = 'var(--border)' }}
          >✕</button>
        </div>

        {/* Tab bar */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', marginBottom: 8 }}>
          {tabBtn('details', 'DETAILS')}
          {tabBtn('notes',   'NOTES')}
          {tabBtn('ai',      '⬡ AI RUNS')}
          {tabBtn('edit',    'EDIT')}
        </div>

        {/* Tab content */}
        {activeTab === 'details' && (
          <TaskDetailView
            task={task}
            projectId={projectId}
            members={members}
            token={token}
            allTasks={allTasks}
            copied={copied}
            onCopySessionId={handleCopySessionId}
          />
        )}

        {activeTab === 'notes' && (
          <LabNotesTab
            comments={comments}
            commentBody={commentBody}
            setCommentBody={setCommentBody}
            onSubmit={() => addComment.mutate(commentBody)}
            isPending={addComment.isPending}
          />
        )}

        {activeTab === 'ai' && (
          <AiRunsTab task={task} projectId={projectId} />
        )}

        {activeTab === 'edit' && (
          <TaskEditForm
            editTitle={editTitle}         setEditTitle={setEditTitle}
            editStatus={editStatus}       setEditStatus={setEditStatus}
            editPriority={editPriority}   setEditPriority={setEditPriority}
            editDeadline={editDeadline}   setEditDeadline={setEditDeadline}
            editDescription={editDescription} setEditDescription={setEditDescription}
            editAssigneeId={editAssigneeId}   setEditAssigneeId={setEditAssigneeId}
            onSave={handleSave}
            onDeleteClick={handleDeleteClick}
            isSaving={updateTask.isPending}
            isDeleting={deleteTask.isPending}
            deleteConfirm={deleteConfirm}
            members={members}
          />
        )}
      </div>
    </div>
  )
}
