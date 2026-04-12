import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listTaskDependencies,
  addTaskDependency,
  removeTaskDependency,
  TaskDependency,
} from '../api'

interface DependencyPickerProps {
  projectId: string
  taskId: string
  token: string
  allTasks: Array<{ id: string; title: string }>
}

const monoStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
}

const sectionHeaderStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  cursor: 'pointer',
  userSelect: 'none',
}

const labelStyle: React.CSSProperties = {
  fontSize: 15,
  fontWeight: 700,
  color: 'var(--text-dim)',
  letterSpacing: '0.12em',
  textTransform: 'uppercase' as const,
  fontFamily: 'var(--font-mono)',
}

const subLabelStyle: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 700,
  color: 'var(--text-3)',
  letterSpacing: '0.08em',
  textTransform: 'uppercase' as const,
  fontFamily: 'var(--font-mono)',
  marginBottom: 4,
}

const tagStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 5,
  padding: '2px 8px',
  borderRadius: 4,
  background: 'var(--surface-comment)',
  border: '1px solid var(--border-subtle)',
  color: 'var(--text-2)',
  fontSize: 14,
  fontFamily: 'var(--font-mono)',
}

const removeButtonStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: '#f43f5e',
  cursor: 'pointer',
  padding: '0 2px',
  fontSize: 13,
  lineHeight: 1,
  display: 'flex',
  alignItems: 'center',
}

const selectStyle: React.CSSProperties = {
  flex: 1,
  padding: '4px 7px',
  background: 'var(--surface-input)',
  border: '1px solid var(--border)',
  borderRadius: 4,
  color: 'var(--text)',
  fontSize: 14,
  fontFamily: 'var(--font-mono)',
  outline: 'none',
  boxSizing: 'border-box' as const,
}

const addButtonStyle: React.CSSProperties = {
  padding: '4px 10px',
  background: 'rgba(255,128,21,0.1)',
  border: '1px solid rgba(255,128,21,0.25)',
  borderRadius: 4,
  color: '#ff8015',
  fontSize: 13,
  fontWeight: 700,
  fontFamily: 'var(--font-mono)',
  cursor: 'pointer',
  letterSpacing: '0.06em',
  transition: 'background 0.14s',
  flexShrink: 0,
}

function TaskChip({
  dep,
  taskTitle,
  onRemove,
  isRemoving,
}: {
  dep: TaskDependency
  taskTitle: string
  onRemove: () => void
  isRemoving: boolean
}) {
  return (
    <span style={{ ...tagStyle, opacity: isRemoving ? 0.5 : 1 }}>
      {dep.dep_type === 'soft' && (
        <span title="soft link" style={{ color: '#a78bfa', fontSize: 12 }}>~</span>
      )}
      {taskTitle}
      <button
        onClick={onRemove}
        disabled={isRemoving}
        title="Remove dependency"
        style={removeButtonStyle}
      >×</button>
    </span>
  )
}

export function DependencyPicker({ projectId, taskId, token, allTasks }: DependencyPickerProps) {
  const queryClient = useQueryClient()
  const [expanded, setExpanded] = useState(false)
  const [selectedTaskId, setSelectedTaskId] = useState('')
  const [depType, setDepType] = useState<'hard' | 'soft'>('hard')
  const [addError, setAddError] = useState<string | null>(null)
  const [removeError, setRemoveError] = useState<string | null>(null)
  const [removingId, setRemovingId] = useState<string | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['dependencies', taskId],
    queryFn: () => listTaskDependencies(projectId, taskId, token),
    enabled: expanded && !!token,
  })

  const addMutation = useMutation({
    mutationFn: () => addTaskDependency(projectId, taskId, selectedTaskId, depType, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dependencies', taskId] })
      setSelectedTaskId('')
      setAddError(null)
    },
    onError: (err: Error) => {
      setAddError(err.message ?? 'Failed to add dependency')
    },
  })

  const removeMutation = useMutation({
    mutationFn: (dependsOnId: string) => removeTaskDependency(projectId, taskId, dependsOnId, token),
    onSuccess: (_data, dependsOnId) => {
      queryClient.invalidateQueries({ queryKey: ['dependencies', taskId] })
      if (removingId === dependsOnId) setRemovingId(null)
      setRemoveError(null)
    },
    onError: (err: Error) => {
      setRemovingId(null)
      setRemoveError(err instanceof Error ? err.message : 'Failed to remove dependency')
    },
  })

  function handleRemove(dependsOnId: string) {
    setRemovingId(dependsOnId)
    removeMutation.mutate(dependsOnId)
  }

  function handleAdd() {
    if (!selectedTaskId) return
    setAddError(null)
    addMutation.mutate()
  }

  // Tasks already used as dependencies (to avoid duplicates in dropdown)
  const existingDepIds = new Set((data?.dependencies ?? []).map(d => d.depends_on_id))

  // Filter out current task and already-added deps from picker options
  const availableTasks = allTasks.filter(t => t.id !== taskId && !existingDepIds.has(t.id))

  const hardDeps = (data?.dependencies ?? []).filter(d => d.dep_type === 'hard')
  const softDeps = (data?.dependencies ?? []).filter(d => d.dep_type === 'soft')
  const dependents = data?.dependents ?? []

  function getTitle(id: string): string {
    return allTasks.find(t => t.id === id)?.title ?? id.slice(0, 8) + '…'
  }

  return (
    <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 12 }}>
      {/* Collapsible header */}
      <div
        style={sectionHeaderStyle}
        onClick={() => setExpanded(prev => !prev)}
        role="button"
        aria-expanded={expanded}
      >
        <span style={labelStyle}>Dependencies</span>
        <div style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
        {data && (data.dependencies.length > 0 || data.dependents.length > 0) && (
          <span style={{
            fontSize: 13,
            color: 'var(--text-dim)',
            background: 'var(--border-subtle)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 9,
            padding: '1px 7px',
            fontFamily: 'var(--font-mono)',
          }}>
            {data.dependencies.length + data.dependents.length}
          </span>
        )}
        <span style={{ ...monoStyle, fontSize: 13, color: 'var(--text-3)', marginLeft: 4 }}>
          {expanded ? '▲' : '▼'}
        </span>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {isLoading && (
            <div style={{ fontSize: 13, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
              loading…
            </div>
          )}
          {isError && (
            <div style={{ fontSize: 13, color: '#f43f5e', fontFamily: 'var(--font-mono)' }}>
              Failed to load dependencies.
            </div>
          )}

          {!isLoading && (
            <>
              {/* Blocks (hard deps) */}
              <div>
                <div style={subLabelStyle}>Blocked by (hard)</div>
                {hardDeps.length === 0 ? (
                  <span style={{ fontSize: 13, color: 'var(--text-muted)', fontStyle: 'italic' }}>none</span>
                ) : (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                    {hardDeps.map(dep => (
                      <TaskChip
                        key={dep.depends_on_id}
                        dep={dep}
                        taskTitle={getTitle(dep.depends_on_id)}
                        onRemove={() => handleRemove(dep.depends_on_id)}
                        isRemoving={removingId === dep.depends_on_id}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Soft links */}
              <div>
                <div style={subLabelStyle}>Soft links</div>
                {softDeps.length === 0 ? (
                  <span style={{ fontSize: 13, color: 'var(--text-muted)', fontStyle: 'italic' }}>none</span>
                ) : (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                    {softDeps.map(dep => (
                      <TaskChip
                        key={dep.depends_on_id}
                        dep={dep}
                        taskTitle={getTitle(dep.depends_on_id)}
                        onRemove={() => handleRemove(dep.depends_on_id)}
                        isRemoving={removingId === dep.depends_on_id}
                      />
                    ))}
                  </div>
                )}
              </div>

              {removeError && (
                <div style={{ fontSize: 13, color: '#f43f5e', fontFamily: 'var(--font-mono)' }}>
                  {removeError}
                </div>
              )}

              {/* Dependents (read-only) */}
              {dependents.length > 0 && (
                <div>
                  <div style={subLabelStyle}>Unblocks (dependents)</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                    {dependents.map(dep => (
                      <span key={dep.task_id} style={{ ...tagStyle, opacity: 0.8 }}>
                        {dep.dep_type === 'soft' && (
                          <span style={{ color: '#a78bfa', fontSize: 12 }}>~</span>
                        )}
                        {getTitle(dep.task_id)}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Add dependency */}
              <div>
                <div style={subLabelStyle}>Add dependency</div>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                  <select
                    value={selectedTaskId}
                    onChange={e => setSelectedTaskId(e.target.value)}
                    style={selectStyle}
                    disabled={availableTasks.length === 0}
                  >
                    <option value="">
                      {availableTasks.length === 0 ? 'No tasks available' : 'Pick a task…'}
                    </option>
                    {availableTasks.map(t => (
                      <option key={t.id} value={t.id}>{t.title}</option>
                    ))}
                  </select>

                  {/* Hard / Soft radio */}
                  <label style={{ ...monoStyle, fontSize: 13, color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: 3, cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name={`dep-type-${taskId}`}
                      value="hard"
                      checked={depType === 'hard'}
                      onChange={() => setDepType('hard')}
                      style={{ accentColor: '#ff8015' }}
                    />
                    hard
                  </label>
                  <label style={{ ...monoStyle, fontSize: 13, color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: 3, cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name={`dep-type-${taskId}`}
                      value="soft"
                      checked={depType === 'soft'}
                      onChange={() => setDepType('soft')}
                      style={{ accentColor: '#a78bfa' }}
                    />
                    soft
                  </label>

                  <button
                    onClick={handleAdd}
                    disabled={!selectedTaskId || addMutation.isPending}
                    style={{
                      ...addButtonStyle,
                      opacity: !selectedTaskId || addMutation.isPending ? 0.5 : 1,
                      cursor: !selectedTaskId || addMutation.isPending ? 'not-allowed' : 'pointer',
                    }}
                    onMouseEnter={e => {
                      if (selectedTaskId && !addMutation.isPending)
                        e.currentTarget.style.background = 'rgba(255,128,21,0.2)'
                    }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.1)' }}
                  >
                    {addMutation.isPending ? '…' : '+ ADD'}
                  </button>
                </div>

                {addError && (
                  <div style={{ marginTop: 5, fontSize: 13, color: '#f43f5e', fontFamily: 'var(--font-mono)' }}>
                    {addError}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
