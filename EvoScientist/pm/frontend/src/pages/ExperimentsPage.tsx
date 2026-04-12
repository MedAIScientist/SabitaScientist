import { useState, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Experiment, listPhases } from '../api'
import { ExperimentDetail } from '../components/ExperimentDetail'
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
  const [showDropdown, setShowDropdown] = useState(false)
  const [newName, setNewName] = useState('')
  const [selectedPhaseId, setSelectedPhaseId] = useState<string | null>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!showDropdown) return
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showDropdown])

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

  const createExperimentMutation = useMutation({
    mutationFn: () => api.createExperiment(projectId!, { name: newName.trim() }),
    onSuccess: (exp) => {
      qc.invalidateQueries({ queryKey: ['experiments', projectId] })
      closeModal()
      setSelectedExp(exp)
    },
  })

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
    setShowDropdown(false)
    setModal(type)
  }

  const isExperiment = modal === 'experiment'
  const accent = isExperiment ? '#10b981' : '#ff8015'
  const accentRgb = isExperiment ? '16,185,129' : '34,211,238'
  const isPending = isExperiment ? createExperimentMutation.isPending : createTaskMutation.isPending

  const handleCreate = () => {
    if (!newName.trim()) return
    if (isExperiment) createExperimentMutation.mutate()
    else createTaskMutation.mutate()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      {/* Header */}
      <div style={{
        padding: '0 24px', height: 52,
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 14,
        background: 'var(--surface-header)',
        backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 10, flexShrink: 0,
      }}>
        <button
          onClick={() => navigate(`/projects/${projectId}`)}
          style={{
            cursor: 'pointer', background: 'var(--surface-input)',
            border: '1px solid var(--border)', borderRadius: 6,
            color: 'var(--text-muted)', padding: '3px 9px', fontSize: 22, lineHeight: 1,
            transition: 'color 0.15s, border-color 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.color = '#ff8015'; e.currentTarget.style.borderColor = 'rgba(255,128,21,0.3)' }}
          onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.borderColor = 'var(--border)' }}
        >←</button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', boxShadow: '0 0 6px #10b981', flexShrink: 0 }} />
          <h1 style={{ margin: 0, fontSize: 21, fontWeight: 600, letterSpacing: '0.03em', color: 'var(--text-heading)', fontFamily: 'var(--font-mono)' }}>
            {project?.name ?? '…'} — Experiments
          </h1>
        </div>

        {/* NEW dropdown */}
        <div style={{ marginLeft: 'auto', position: 'relative' }} ref={dropdownRef}>
          <button
            onClick={() => setShowDropdown(v => !v)}
            style={{
              background: 'rgba(255,128,21,0.08)', border: '1px solid rgba(255,128,21,0.22)',
              borderRadius: 4, padding: '5px 14px', color: '#ff8015',
              fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
              letterSpacing: '0.08em', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
              transition: 'background 0.14s',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.15)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,128,21,0.08)' }}
          >
            + NEW
            <span style={{ fontSize: 18, opacity: 0.7, marginLeft: 2 }}>▾</span>
          </button>

          {showDropdown && (
            <div style={{
              position: 'absolute', top: 'calc(100% + 6px)', right: 0,
              background: 'var(--surface-panel)',
              border: '1px solid var(--border)',
              borderRadius: 6, overflow: 'hidden',
              boxShadow: '0 8px 24px rgba(0,0,0,0.35)',
              minWidth: 160, zIndex: 20,
              animation: 'fadeInUp 0.12s ease',
            }}>
              <DropdownItem
                icon="⚗"
                label="EXPERIMENT"
                sub="Lab experiment with notes & results"
                color="#10b981"
                onClick={() => openModal('experiment')}
              />
              <div style={{ height: 1, background: 'var(--border-subtle)' }} />
              <DropdownItem
                icon="✦"
                label="TASK"
                sub="Kanban task added to Planned column"
                color="#ff8015"
                onClick={() => openModal('task')}
              />
            </div>
          )}
        </div>
      </div>

      {/* Create modal */}
      {modal && (
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
            <div style={{ fontSize: 20, fontWeight: 700, color: accent, fontFamily: 'var(--font-mono)', marginBottom: 14, letterSpacing: '0.1em' }}>
              {isExperiment ? '⚗ NEW EXPERIMENT' : '✦ NEW TASK'}
            </div>
            <input
              value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder={isExperiment ? 'Experiment name…' : 'Task title…'}
              autoFocus
              onKeyDown={e => e.key === 'Enter' && handleCreate()}
              style={{
                width: '100%', boxSizing: 'border-box',
                background: 'var(--surface-input)',
                border: `1px solid rgba(${accentRgb},0.2)`,
                borderRadius: 5, color: 'var(--text)', fontSize: 22, padding: '8px 10px',
                fontFamily: 'inherit', outline: 'none', marginBottom: 14,
              }}
            />
            {!isExperiment && (
              <p style={{ fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginBottom: 14, marginTop: -8 }}>
                Task will appear in the PLANNED column on the board.
              </p>
            )}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={closeModal}
                style={{
                  background: 'var(--surface-input)', border: '1px solid var(--border-subtle)',
                  borderRadius: 4, padding: '6px 14px', color: 'var(--text-muted)',
                  fontSize: 16, cursor: 'pointer', fontFamily: 'var(--font-mono)',
                }}
              >CANCEL</button>
              <button
                onClick={handleCreate}
                disabled={!newName.trim() || isPending}
                style={{
                  background: `rgba(${accentRgb},0.1)`, border: `1px solid rgba(${accentRgb},0.28)`,
                  borderRadius: 4, padding: '6px 14px', color: accent,
                  fontSize: 16, fontWeight: 700, cursor: 'pointer', fontFamily: 'var(--font-mono)',
                  opacity: !newName.trim() ? 0.4 : 1,
                }}
              >CREATE</button>
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
          <div style={{ textAlign: 'center', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 20, marginTop: 60 }}>
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

function DropdownItem({
  icon, label, sub, color, onClick,
}: {
  icon: string; label: string; sub: string; color: string; onClick: () => void
}) {
  const [hovered, setHovered] = useState(false)
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex', alignItems: 'flex-start', gap: 10,
        width: '100%', padding: '10px 14px', border: 'none', cursor: 'pointer', textAlign: 'left',
        background: hovered ? 'var(--surface-card-hover)' : 'transparent',
        transition: 'background 0.1s',
      }}
    >
      <span style={{ fontSize: 21, flexShrink: 0, marginTop: 1 }}>{icon}</span>
      <div>
        <div style={{ fontSize: 16, fontWeight: 700, color, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>
          {label}
        </div>
        <div style={{ fontSize: 15, color: 'var(--text-dim)', marginTop: 1, lineHeight: 1.4 }}>
          {sub}
        </div>
      </div>
    </button>
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
        <div style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-heading)', lineHeight: 1.3 }}>{exp.name}</div>
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
      {exp.tags.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
          {exp.tags.map(tag => (
            <span key={tag} style={{ fontSize: 16, color: 'var(--text-3)', background: 'var(--surface-input)', border: '1px solid var(--border-subtle)', borderRadius: 2, padding: '1px 4px' }}>
              {tag}
            </span>
          ))}
        </div>
      )}
      {exp.deadline && (
        <div style={{ fontSize: 15, color: 'var(--text-dim)', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
          DEADLINE: {exp.deadline}
        </div>
      )}
    </div>
  )
}
