import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ProjectHeader } from '../components/ProjectHeader'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Experiment, listPhases } from '../api'
import { ExperimentDetail } from '../components/ExperimentDetail'
import { NewExperimentDialog } from '../components/experiment/NewExperimentDialog'
import { useAuth } from '../auth'

const STATUS_COLORS: Record<string, string> = {
  planned: '#f59e0b', running: '#ff8015', completed: '#10b981',
}

type ModalType = 'experiment' | 'task' | null

export function ExperimentsPage() {
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { token } = useAuth()
  const [selectedExp, setSelectedExp] = useState<Experiment | null>(null)
  const [modal, setModal] = useState<ModalType>(null)
  const [newName, setNewName] = useState('')
  const [selectedPhaseId, setSelectedPhaseId] = useState<string | null>(null)

  useEffect(() => {
    setSelectedPhaseId(null)
  }, [projectId])

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.getProject(projectId!),
    enabled: Boolean(projectId),
  })

  const { data: experiments = [] } = useQuery({
    queryKey: ['experiments', projectId],
    queryFn: () => api.listExperiments(projectId!),
    enabled: Boolean(projectId),
  })

  const { data: phases = [] } = useQuery({
    queryKey: ['phases', projectId],
    queryFn: () => listPhases(projectId!, token!),
    enabled: Boolean(projectId) && Boolean(token),
  })

  const filteredExperiments = selectedPhaseId === null
    ? experiments
    : experiments.filter(e => e.phase_id === selectedPhaseId)

  const createTaskMutation = useMutation({
    mutationFn: () => api.createTask(projectId!, { title: newName.trim(), status: 'todo' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks', projectId] })
      closeModal()
    },
  })

  const closeModal = () => {
    setModal(null)
    setNewName('')
  }

  const openModal = (type: ModalType) => {
    setModal(type)
  }

  const accent = '#ff8015'
  const accentRgb = '255,128,21'

  const handleCreate = () => {
    if (!newName.trim()) return
    createTaskMutation.mutate()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <ProjectHeader projectId={projectId!} name={project?.name} actions={<>
        <button className="btn" onClick={() => openModal('task')}>+ New task</button>
        <button className="btn btn-primary" onClick={() => openModal('experiment')}>+ New experiment</button>
      </>} />

      {/* Create experiment — a dedicated dialog that also captures the phase, so
          the new experiment does not land in "Unassigned" and need a second trip
          through the detail panel. */}
      {modal === 'experiment' && (
        <NewExperimentDialog
          projectId={projectId!}
          phases={phases}
          defaultPhaseId={selectedPhaseId}
          onCreated={exp => { setModal(null); setSelectedExp(exp) }}
          onClose={() => setModal(null)}
        />
      )}

      {/* Create task */}
      {modal === 'task' && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50,
        }}
          onClick={e => { if (e.target === e.currentTarget) closeModal() }}
        >
          <div style={{
            background: 'var(--surface-panel)',
            border: `1px solid rgba(${accentRgb},0.22)`,
            borderRadius: 10, padding: 24, width: 360,
            animation: 'fadeInUp 0.15s ease',
          }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: accent, fontFamily: 'var(--font-mono)', marginBottom: 14, letterSpacing: '0.04em' }}>
              ✦ New task
            </div>
            <input
              value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder="Task title…"
              autoFocus
              onKeyDown={e => e.key === 'Enter' && handleCreate()}
              style={{
                width: '100%', boxSizing: 'border-box',
                background: 'var(--surface-input)',
                border: `1px solid rgba(${accentRgb},0.2)`,
                borderRadius: 5, color: 'var(--text)', fontSize: 17, padding: '8px 10px',
                fontFamily: 'inherit', outline: 'none', marginBottom: 14,
              }}
            />
            <p style={{ fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginBottom: 14, marginTop: -8 }}>
              Task will appear in the PLANNED column on the board.
            </p>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={closeModal}
                style={{
                  background: 'var(--surface-input)', border: '1px solid var(--border-subtle)',
                  borderRadius: 4, padding: '6px 14px', color: 'var(--text-muted)',
                  fontSize: 16, cursor: 'pointer', fontFamily: 'var(--font-mono)',
                }}
              >Cancel</button>
              <button
                onClick={handleCreate}
                disabled={!newName.trim() || createTaskMutation.isPending}
                style={{
                  background: `rgba(${accentRgb},0.1)`, border: `1px solid rgba(${accentRgb},0.28)`,
                  borderRadius: 4, padding: '6px 14px', color: accent,
                  fontSize: 16, fontWeight: 700, cursor: 'pointer', fontFamily: 'var(--font-mono)',
                  opacity: !newName.trim() ? 0.4 : 1,
                }}
              >Create</button>
            </div>
          </div>
        </div>
      )}

      {/* Experiment grid */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
        {/* Phase filter chips */}
        {phases.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 18 }}>
            <PhaseChip
              label="All"
              color="#64748b"
              active={selectedPhaseId === null}
              onClick={() => setSelectedPhaseId(null)}
            />
            {phases.map(phase => (
              <PhaseChip
                key={phase.id}
                label={phase.name}
                color={phase.color}
                active={selectedPhaseId === phase.id}
                onClick={() => setSelectedPhaseId(phase.id)}
              />
            ))}
          </div>
        )}

        {filteredExperiments.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 16, marginTop: 60 }}>
            {experiments.length === 0 ? 'NO EXPERIMENTS YET' : 'NO EXPERIMENTS IN THIS PHASE'}
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
            {filteredExperiments.map(exp => (
              <ExperimentCard key={exp.id} exp={exp} onClick={() => setSelectedExp(exp)} />
            ))}
          </div>
        )}
      </div>

      {selectedExp && (
        <ExperimentDetail
          key={selectedExp.id}
          experiment={selectedExp}
          projectId={projectId!}
          onClose={() => setSelectedExp(null)}
        />
      )}
    </div>
  )
}


function PhaseChip({
  label, color, active, onClick,
}: {
  label: string; color: string; active: boolean; onClick: () => void
}) {
  const [hovered, setHovered] = useState(false)
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 5,
        padding: '3px 10px', borderRadius: 20,
        border: active ? `1px solid ${color}` : '1px solid var(--border-subtle)',
        background: active ? `${color}22` : hovered ? 'var(--surface-card-hover)' : 'var(--surface-input)',
        color: active ? color : hovered ? 'var(--text)' : 'var(--text-muted)',
        fontSize: 15, fontFamily: 'var(--font-mono)', fontWeight: active ? 700 : 400,
        cursor: 'pointer', transition: 'all 0.12s', letterSpacing: '0.04em',
        outline: 'none',
      }}
    >
      {label !== 'All' && (
        <span style={{
          width: 7, height: 7, borderRadius: '50%',
          background: color,
          boxShadow: active ? `0 0 5px ${color}` : 'none',
          flexShrink: 0,
        }} />
      )}
      {label}
    </button>
  )
}

function ExperimentCard({ exp, onClick }: { exp: Experiment; onClick: () => void }) {
  const color = STATUS_COLORS[exp.status] ?? '#64748b'
  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--surface-card)', border: '1px solid var(--border-subtle)',
        borderRadius: 8, padding: '14px 16px', cursor: 'pointer',
        transition: 'border-color 0.15s',
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border)')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border-subtle)')}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div style={{ fontSize: 17, fontWeight: 600, color: 'var(--text-heading)', lineHeight: 1.3 }}>{exp.name}</div>
        <span style={{
          fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
          color, background: `${color}18`, border: `1px solid ${color}33`,
          borderRadius: 2, padding: '1px 5px', flexShrink: 0, marginLeft: 8,
        }}>
          {exp.status.toUpperCase()}
        </span>
      </div>
      {exp.hypothesis && (
        <p style={{ fontSize: 16, color: 'var(--text-2)', margin: '0 0 8px', lineHeight: 1.5, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
          {exp.hypothesis}
        </p>
      )}

      {exp.deadline && (
        <div style={{ fontSize: 15, color: 'var(--text-dim)', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
          DEADLINE: {exp.deadline}
        </div>
      )}

      {((exp.linked_task_count ?? 0) > 0 || (exp.linked_asset_count ?? 0) > 0) && (
        <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
          {(exp.linked_task_count ?? 0) > 0 && (
            <span style={{
              fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)',
              background: 'var(--surface-input)', border: '1px solid var(--border)',
              borderRadius: 3, padding: '1px 6px',
            }}>🔗 {exp.linked_task_count} task{exp.linked_task_count === 1 ? '' : 's'}</span>
          )}
          {/* Surfaces the DATA tab: without this there is no hint on the card
              that an experiment is traced to datasets or imaging artefacts. */}
          {(exp.linked_asset_count ?? 0) > 0 && (
            <span style={{
              fontSize: 13, fontFamily: 'var(--font-mono)', color: '#8b5cf6',
              background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.25)',
              borderRadius: 3, padding: '1px 6px',
            }}>🗄 {exp.linked_asset_count} data</span>
          )}
        </div>
      )}
    </div>
  )
}
