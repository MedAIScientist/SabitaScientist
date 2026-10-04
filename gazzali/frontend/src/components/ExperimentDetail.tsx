import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Experiment, ExperimentEntry, Task } from '../api'
import { EntryEditor } from './EntryEditor'
import { AttachmentList } from './AttachmentList'
import { ExperimentDataTab } from './experiment/ExperimentDataTab'
import { ExperimentMetricsTab } from './experiment/ExperimentMetricsTab'
import { ResearchRunsTab } from './experiment/ResearchRunsTab'

const STATUS_META: Record<string, { color: string; label: string }> = {
  planned:   { color: '#f59e0b', label: 'Planned' },
  running:   { color: '#ff8015', label: 'Running' },
  completed: { color: '#10b981', label: 'Completed' },
  abandoned: { color: '#6b7280', label: 'Abandoned' },
}

interface Phase { id: string; name: string; color?: string }

interface Props {
  experiment: Experiment
  projectId: string
  onClose: () => void
  phases?: Phase[]
}

type Tab = 'overview' | 'data' | 'runs' | 'notes' | 'results'

export function ExperimentDetail({ experiment, projectId, onClose, phases }: Props) {
  const qc = useQueryClient()
  const [tab, setTab] = useState<Tab>('overview')
  const [showEditor, setShowEditor] = useState(false)
  const [editingEntry, setEditingEntry] = useState<ExperimentEntry | null>(null)
  const [taskSearch, setTaskSearch] = useState('')
  const [isEditing, setIsEditing] = useState(false)
  const [editName, setEditName] = useState(experiment.name)
  const [editStatus, setEditStatus] = useState<string>(experiment.status)
  const [editHypothesis, setEditHypothesis] = useState(experiment.hypothesis ?? '')
  const [editProtocol, setEditProtocol] = useState(experiment.protocol ?? '')
  const [editDeadline, setEditDeadline] = useState(experiment.deadline ?? '')
  const [editPhaseId, setEditPhaseId] = useState(experiment.phase_id ?? '')

  const status = STATUS_META[experiment.status] ?? STATUS_META.planned

  // Entries query — filtered by tab
  const entryType = tab === 'notes' ? 'note' : tab === 'results' ? 'result' : undefined
  const { data: entries = [] } = useQuery({
    queryKey: ['entries', experiment.id, entryType],
    queryFn: () => api.listEntries(projectId, experiment.id, entryType),
    enabled: tab !== 'overview',
  })

  const { data: linkedTasks = [] } = useQuery({
    queryKey: ['linked-tasks', experiment.id],
    queryFn: () => api.listLinkedTasks(projectId, experiment.id),
    enabled: tab === 'overview',
  })

  const { data: allTasks = [] } = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => api.listTasks(projectId),
    enabled: tab === 'overview' && taskSearch.length > 0,
  })

  const createEntryMutation = useMutation({
    mutationFn: (data: { title: string; body: string }) =>
      api.createEntry(projectId, experiment.id, { type: entryType as 'note' | 'result', ...data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entries', experiment.id] })
      setShowEditor(false)
    },
  })

  const updateEntryMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { title: string; body: string } }) =>
      api.updateEntry(projectId, experiment.id, id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entries', experiment.id] })
      setEditingEntry(null)
    },
  })

  const deleteEntryMutation = useMutation({
    mutationFn: (entryId: string) => api.deleteEntry(projectId, experiment.id, entryId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['entries', experiment.id] }),
  })

  const linkTaskMutation = useMutation({
    mutationFn: (taskId: string) => api.linkTask(projectId, experiment.id, taskId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['linked-tasks', experiment.id] })
      qc.invalidateQueries({ queryKey: ['experiments', projectId] })
      setTaskSearch('')
    },
  })

  const unlinkTaskMutation = useMutation({
    mutationFn: (taskId: string) => api.unlinkTask(projectId, experiment.id, taskId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['linked-tasks', experiment.id] }),
  })

  const updateExperimentMutation = useMutation({
    mutationFn: (data: { name?: string; hypothesis?: string; protocol?: string; status?: string; deadline?: string | null; phase_id?: string | null }) =>
      api.updateExperiment(projectId, experiment.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['experiment', experiment.id] })
      qc.invalidateQueries({ queryKey: ['experiments', projectId] })
      setIsEditing(false)
    },
  })

  const searchResults = taskSearch.length > 0
    ? allTasks.filter((t: Task) =>
        t.title.toLowerCase().includes(taskSearch.toLowerCase()) &&
        !linkedTasks.some((lt: Task) => lt.id === t.id)
      )
    : []

  const tabStyle = (t: Tab): React.CSSProperties => ({
    padding: '6px 10px', fontSize: 14, fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap', flex: 'none',
    color: tab === t ? 'var(--accent)' : 'var(--text-3)',
    background: 'none', border: 'none', borderBottomStyle: 'solid',
    borderBottomWidth: 2, borderBottomColor: tab === t ? 'var(--accent)' : 'transparent',
    cursor: 'pointer', fontWeight: tab === t ? 700 : 400,
  })

  return (
    <div style={{
      position: 'fixed', right: 0, top: 0, bottom: 0, width: 420,
      background: 'var(--surface-panel)', borderLeft: '1px solid var(--border)',
      zIndex: 30, display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 16px 10px', borderBottom: '1px solid var(--border-subtle)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 8 }}>
          <div>
            <div style={{ fontSize: 17, fontWeight: 600, color: 'var(--text-heading)', marginBottom: 4 }}>
              {experiment.name}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{
                fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
                color: status.color, background: `${status.color}18`,
                border: `1px solid ${status.color}33`,
                borderRadius: 2, padding: '1px 5px',
              }}>
                {status.label}
              </span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <button
              onClick={() => {
                if (isEditing) {
                  updateExperimentMutation.mutate({
                    name: editName,
                    status: editStatus,
                    hypothesis: editHypothesis || undefined,
                    protocol: editProtocol || undefined,
                    deadline: editDeadline || undefined,
                    // null, not undefined: undefined omits the key and the API
                    // would leave the old phase in place, so picking "No phase"
                    // could never un-assign it.
                    phase_id: editPhaseId || null,
                  })
                } else {
                  setEditName(experiment.name)
                  setEditStatus(experiment.status)
                  setEditHypothesis(experiment.hypothesis ?? '')
                  setEditProtocol(experiment.protocol ?? '')
                  setEditDeadline(experiment.deadline ?? '')
                  setEditPhaseId(experiment.phase_id ?? '')
                  setIsEditing(true)
                }
              }}
              style={{
                background: isEditing ? 'rgba(16,185,129,0.12)' : 'rgba(var(--accent-rgb),0.08)',
                border: isEditing ? '1px solid rgba(16,185,129,0.3)' : '1px solid rgba(var(--accent-rgb),0.18)',
                borderRadius: 4, color: isEditing ? '#10b981' : 'var(--accent)', fontSize: 15,
                cursor: 'pointer', padding: '2px 8px',
                fontFamily: 'var(--font-mono)', fontWeight: 700,
              }}
              title={isEditing ? 'Save changes' : 'Edit experiment'}
            >
              {isEditing ? '💾 Save' : '✎ Edit'}
            </button>
            <button
              onClick={onClose}
              aria-label="✕"
              style={{ background: 'none', border: 'none', color: 'var(--text-3)', fontSize: 20, cursor: 'pointer', padding: 4 }}
            >
              ✕
            </button>
          </div>
        </div>

        {/* Tab bar */}
        <div role="tablist" aria-label="Experiment" style={{ display: 'flex', flexWrap: 'wrap', columnGap: 2, borderBottom: '1px solid var(--border-subtle)', marginTop: 4 }}>
          {([
            ['overview', 'Overview', undefined],
            ['notes', 'Notes', undefined],
            ['results', 'Results', undefined],
            ['data', 'Data', undefined],
            ['runs', 'AI runs', 'Automated experiment runs (AutoResearchClaw)'],
          ] as [Tab, string, string | undefined][]).map(([t, label, title]) => (
            <button key={t} role="tab" aria-selected={tab === t} title={title} style={tabStyle(t)}
              onClick={() => { setTab(t); if (t === 'notes' || t === 'results') setShowEditor(false) }}>{label}</button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px' }}>
        {tab === 'overview' && !isEditing && (
          <OverviewTab
            experiment={experiment}
            linkedTasks={linkedTasks}
            taskSearch={taskSearch}
            setTaskSearch={setTaskSearch}
            searchResults={searchResults}
            onLink={(id: string) => linkTaskMutation.mutate(id)}
            onUnlink={(id: string) => unlinkTaskMutation.mutate(id)}
            phases={phases}
          />
        )}

        {tab === 'overview' && isEditing && (
          <div>
            {isEditing && (
              <button
                onClick={() => setIsEditing(false)}
                style={{
                  background: 'rgba(244,63,94,0.06)', border: '1px solid rgba(244,63,94,0.15)',
                  borderRadius: 4, color: '#f43f5e', fontSize: 14, cursor: 'pointer',
                  fontFamily: 'var(--font-mono)', padding: '3px 8px', marginBottom: 10,
                }}
              >✕ Cancel</button>
            )}
            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>Name</label>
              <input value={editName} onChange={e => setEditName(e.target.value)}
                style={{ width: '100%', boxSizing: 'border-box', padding: '8px 11px', background: 'var(--surface-input)',
                  border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontSize: 16, outline: 'none' }} />
            </div>
            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>Status</label>
              <select value={editStatus} onChange={e => setEditStatus(e.target.value)}
                style={{ width: '100%', boxSizing: 'border-box', padding: '8px 11px', background: 'var(--surface-input)',
                  border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontSize: 16, outline: 'none' }}>
                {Object.entries(STATUS_META).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </select>
            </div>
            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>Hypothesis</label>
              <textarea value={editHypothesis} onChange={e => setEditHypothesis(e.target.value)} rows={4}
                style={{ width: '100%', boxSizing: 'border-box', padding: '8px 11px', background: 'var(--surface-input)',
                  border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontSize: 15, outline: 'none', resize: 'vertical' }} />
            </div>
            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>Protocol</label>
              <textarea value={editProtocol} onChange={e => setEditProtocol(e.target.value)} rows={4}
                style={{ width: '100%', boxSizing: 'border-box', padding: '8px 11px', background: 'var(--surface-input)',
                  border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontSize: 15, outline: 'none', resize: 'vertical' }} />
            </div>
            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>Phase</label>
              <select value={editPhaseId} onChange={e => setEditPhaseId(e.target.value)}
                style={{ width: '100%', boxSizing: 'border-box', padding: '8px 11px', background: 'var(--surface-input)',
                  border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontSize: 16, outline: 'none' }}>
                <option value="">No phase</option>
                {(phases ?? []).map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>Deadline</label>
              <input type="date" value={editDeadline} onChange={e => setEditDeadline(e.target.value)}
                style={{ width: '100%', boxSizing: 'border-box', padding: '8px 11px', background: 'var(--surface-input)',
                  border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontSize: 16, outline: 'none' }} />
            </div>
          </div>
        )}

        {tab === 'data' && (
          <ExperimentDataTab projectId={projectId} experimentId={experiment.id} />
        )}

        {tab === 'runs' && (
          <ResearchRunsTab projectId={projectId} experimentId={experiment.id} hypothesis={experiment.hypothesis} />
        )}

        {tab === 'results' && (
          <div style={{ marginBottom: 18 }}>
            <ExperimentMetricsTab projectId={projectId} experimentId={experiment.id} />
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-2)', margin: '14px 0 0', borderTop: '1px solid var(--border-subtle)', paddingTop: 12 }}>Written results</div>
          </div>
        )}

        {(tab === 'notes' || tab === 'results') && (
          <EntriesTab
            entries={entries}
            type={tab === 'notes' ? 'note' : 'result'}
            editingEntry={editingEntry}
            showEditor={showEditor}
            onAdd={() => { setShowEditor(true); setEditingEntry(null) }}
            onEdit={(entry: ExperimentEntry) => { setEditingEntry(entry); setShowEditor(false) }}
            onDelete={(id: string) => deleteEntryMutation.mutate(id)}
            onSaveNew={(data: { title: string; body: string }) => createEntryMutation.mutate(data)}
            onSaveEdit={(data: { title: string; body: string }) => editingEntry && updateEntryMutation.mutate({ id: editingEntry.id, data })}
            onCancelEditor={() => { setShowEditor(false); setEditingEntry(null) }}
            projectId={projectId}
            expId={experiment.id}
          />
        )}
      </div>

    </div>
  )
}

function OverviewTab({
  experiment, linkedTasks, taskSearch, setTaskSearch,
  searchResults, onLink, onUnlink, phases,
}: {
  experiment: Experiment
  linkedTasks: Task[]
  taskSearch: string
  setTaskSearch: (s: string) => void
  searchResults: Task[]
  onLink: (id: string) => void
  onUnlink: (id: string) => void
  phases?: Phase[]
}) {
  const fieldLabel: React.CSSProperties = {
    fontSize: 15, fontWeight: 700, color: 'var(--text-dim)',
    letterSpacing: '0.04em', fontFamily: 'var(--font-mono)',
    marginBottom: 4, marginTop: 10, display: 'block',
  }
  const currentPhase = phases?.find(p => p.id === experiment.phase_id)

  return (
    <div>
      {currentPhase && (
        <>
          <span style={fieldLabel}>Phase</span>
          <p style={{
            fontSize: 16, color: 'var(--text-2)', margin: '0 0 8px',
            display: 'inline-block',
            background: `${currentPhase.color ?? '#ff8015'}14`,
            border: `1px solid ${currentPhase.color ?? '#ff8015'}30`,
            borderRadius: 4, padding: '2px 10px',
            fontFamily: 'var(--font-mono)', fontWeight: 700,
          }}>
            {currentPhase.name}
          </p>
        </>
      )}
      {experiment.hypothesis && (
        <>
          <span style={fieldLabel}>Hypothesis</span>
          <p style={{ fontSize: 16, color: 'var(--text-2)', margin: '0 0 8px', lineHeight: 1.6 }}>
            {experiment.hypothesis}
          </p>
        </>
      )}
      {experiment.protocol && (
        <>
          <span style={fieldLabel}>Protocol</span>
          <pre style={{ fontSize: 16, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', whiteSpace: 'pre-wrap', margin: '0 0 8px' }}>
            {experiment.protocol}
          </pre>
        </>
      )}
      {experiment.deadline && (
        <>
          <span style={fieldLabel}>Deadline</span>
          <p style={{ fontSize: 16, color: 'var(--text-2)', margin: '0 0 8px' }}>{experiment.deadline}</p>
        </>
      )}

      <span style={fieldLabel}>Linked tasks</span>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
        {linkedTasks.map((t: Task) => (
          <span key={t.id} style={{
            fontSize: 15, color: 'var(--accent)', background: 'rgba(var(--accent-rgb),0.06)',
            border: '1px solid rgba(var(--accent-rgb),0.18)', borderRadius: 3, padding: '2px 7px',
            display: 'flex', alignItems: 'center', gap: 4,
          }}>
            {t.title}
            <button
              onClick={() => onUnlink(t.id)}
              style={{ background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer', fontSize: 16, padding: 0 }}
            >
              ✕
            </button>
          </span>
        ))}
        {linkedTasks.length === 0 && (
          <span style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>No linked tasks</span>
        )}
      </div>
      <input
        value={taskSearch}
        onChange={e => setTaskSearch(e.target.value)}
        placeholder="Search tasks to link…"
        style={{
          width: '100%', boxSizing: 'border-box',
          background: 'var(--surface-input)', border: '1px solid var(--border)',
          borderRadius: 4, color: 'var(--text-2)', fontSize: 16, padding: '5px 8px',
          fontFamily: 'inherit', outline: 'none',
        }}
      />
      {searchResults.map((t: Task) => (
        <button
          key={t.id}
          onClick={() => onLink(t.id)}
          style={{
            display: 'block', width: '100%', textAlign: 'left',
            background: 'rgba(var(--accent-rgb),0.04)', border: '1px solid rgba(var(--accent-rgb),0.1)',
            borderRadius: 3, padding: '4px 8px', color: 'var(--text-2)', fontSize: 16,
            cursor: 'pointer', marginTop: 2,
          }}
        >
          + {t.title}
        </button>
      ))}
    </div>
  )
}

function EntriesTab({
  entries, type, editingEntry, showEditor,
  onAdd, onEdit, onDelete, onSaveNew, onSaveEdit, onCancelEditor, pendingBody,
  projectId, expId,
}: {
  entries: ExperimentEntry[]
  type: 'note' | 'result'
  editingEntry: ExperimentEntry | null
  showEditor: boolean
  onAdd: () => void
  onEdit: (e: ExperimentEntry) => void
  onDelete: (id: string) => void
  onSaveNew: (data: { title: string; body: string }) => void
  onSaveEdit: (data: { title: string; body: string }) => void
  onCancelEditor: () => void
  pendingBody?: string
  projectId: string
  expId: string
}) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const label = type === 'note' ? 'Note' : 'Result'
  const accent = type === 'note' ? '#ff8015' : '#10b981'

  return (
    <div>
      <button
        onClick={onAdd}
        style={{
          width: '100%', background: `${accent}14`, border: `1px solid ${accent}55`,
          borderRadius: 4, padding: '6px', color: accent, fontSize: 15, fontWeight: 700,
          fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', cursor: 'pointer', marginBottom: 10,
        }}
      >
        + ADD {label}
      </button>

      {showEditor && (
        <div style={{ marginBottom: 10 }}>
          <EntryEditor type={type} onSave={onSaveNew} onCancel={onCancelEditor} initialBody={pendingBody ?? ''} />
        </div>
      )}

      {entries.length === 0 && !showEditor && (
        <div style={{ fontSize: 15, color: 'var(--text-dim)', textAlign: 'center', fontFamily: 'var(--font-mono)', marginTop: 12 }}>
          NO {label}S YET
        </div>
      )}

      {entries.map(entry => (
        <div key={entry.id} style={{ marginBottom: 6 }}>
          {editingEntry?.id === entry.id ? (
            <EntryEditor
              type={type}
              initialTitle={entry.title}
              initialBody={entry.body}
              onSave={onSaveEdit}
              onCancel={onCancelEditor}
            />
          ) : (
            <div style={{ border: `1px solid var(--border)`, borderRadius: 4, overflow: 'hidden' }}>
              <button
                onClick={() => setExpanded(expanded === entry.id ? null : entry.id)}
                style={{
                  width: '100%', background: 'var(--surface-2)', padding: '6px 8px',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  border: 'none', cursor: 'pointer',
                }}
              >
                <span style={{ fontSize: 16, color: 'var(--text)', fontWeight: 600 }}>{entry.title}</span>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <span style={{ fontSize: 16, color: 'var(--text-dim)' }}>{entry.created_at.slice(0, 10)}</span>
                  <span style={{ fontSize: 15, color: 'var(--text-3)' }}>{expanded === entry.id ? '▲' : '▼'}</span>
                </div>
              </button>
              {expanded === entry.id && (
                <div style={{ padding: '8px 10px', background: 'var(--surface-input)' }}>
                  {entry.body ? (
                    <pre style={{ fontSize: 15, color: 'var(--text-2)', fontFamily: 'var(--font-mono)', whiteSpace: 'pre-wrap', margin: '0 0 8px', lineHeight: 1.6 }}>
                      {entry.body}
                    </pre>
                  ) : (
                    <p style={{ fontSize: 15, color: 'var(--text-dim)', margin: '0 0 8px' }}>No content.</p>
                  )}
                  <AttachmentList
                    projectId={projectId}
                    expId={expId}
                    entryId={entry.id}
                    accent={accent}
                  />
                  <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
                    <button onClick={() => onEdit(entry)} style={{ fontSize: 15, color: 'var(--accent)', background: 'rgba(var(--accent-rgb),0.06)', border: '1px solid rgba(var(--accent-rgb),0.15)', borderRadius: 2, padding: '2px 6px', cursor: 'pointer', fontFamily: 'var(--font-mono)' }}>✏ Edit</button>
                    <button onClick={() => onDelete(entry.id)} style={{ fontSize: 15, color: '#f43f5e', background: 'rgba(244,63,94,0.06)', border: '1px solid rgba(244,63,94,0.15)', borderRadius: 2, padding: '2px 6px', cursor: 'pointer', fontFamily: 'var(--font-mono)' }}>✕ Delete</button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
