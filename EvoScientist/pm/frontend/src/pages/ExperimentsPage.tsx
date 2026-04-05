import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Experiment } from '../api'
import { ExperimentDetail } from '../components/ExperimentDetail'

const STATUS_COLORS: Record<string, string> = {
  planned: '#f59e0b', running: '#22d3ee', completed: '#10b981',
}

export function ExperimentsPage() {
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [selectedExp, setSelectedExp] = useState<Experiment | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')

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

  const createMutation = useMutation({
    mutationFn: () => api.createExperiment(projectId!, { name: newName.trim() }),
    onSuccess: (exp) => {
      qc.invalidateQueries({ queryKey: ['experiments', projectId] })
      setShowCreate(false)
      setNewName('')
      setSelectedExp(exp)
    },
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#070b12', color: '#f1f5f9' }}>
      {/* Header */}
      <div style={{
        padding: '0 24px', height: 52,
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 14,
        background: 'rgba(13,21,38,0.85)',
        backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 10, flexShrink: 0,
      }}>
        <button
          onClick={() => navigate(`/projects/${projectId}`)}
          style={{
            cursor: 'pointer', background: 'rgba(100,140,200,0.07)',
            border: '1px solid rgba(100,140,200,0.14)', borderRadius: 6,
            color: '#64748b', padding: '3px 9px', fontSize: 15, lineHeight: 1,
          }}
        >←</button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', boxShadow: '0 0 6px #10b981', flexShrink: 0 }} />
          <h1 style={{ margin: 0, fontSize: 14, fontWeight: 600, letterSpacing: '0.03em', color: '#f1f5f9', fontFamily: 'var(--font-mono)' }}>
            {project?.name ?? '…'} — Experiments
          </h1>
        </div>

        <div style={{ marginLeft: 'auto' }}>
          <button
            onClick={() => setShowCreate(true)}
            style={{
              background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.28)',
              borderRadius: 4, padding: '4px 12px', color: '#10b981',
              fontSize: 10, fontWeight: 700, fontFamily: 'var(--font-mono)',
              letterSpacing: '0.08em', cursor: 'pointer',
            }}
          >
            + NEW EXPERIMENT
          </button>
        </div>
      </div>

      {/* Create modal */}
      {showCreate && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50,
        }}>
          <div style={{ background: '#0d1526', border: '1px solid rgba(100,140,200,0.2)', borderRadius: 8, padding: 24, width: 360 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#22d3ee', fontFamily: 'var(--font-mono)', marginBottom: 12 }}>
              NEW EXPERIMENT
            </div>
            <input
              value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder="Experiment name…"
              autoFocus
              onKeyDown={e => e.key === 'Enter' && newName.trim() && createMutation.mutate()}
              style={{
                width: '100%', boxSizing: 'border-box',
                background: '#070b12', border: '1px solid rgba(100,140,200,0.18)',
                borderRadius: 4, color: '#e2e8f0', fontSize: 13, padding: '8px 10px',
                fontFamily: 'inherit', outline: 'none', marginBottom: 12,
              }}
            />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => { setShowCreate(false); setNewName('') }}
                style={{ background: 'rgba(100,140,200,0.06)', border: '1px solid rgba(100,140,200,0.14)', borderRadius: 4, padding: '5px 12px', color: '#64748b', fontSize: 10, cursor: 'pointer', fontFamily: 'var(--font-mono)' }}
              >
                CANCEL
              </button>
              <button
                onClick={() => createMutation.mutate()}
                disabled={!newName.trim()}
                style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.28)', borderRadius: 4, padding: '5px 12px', color: '#10b981', fontSize: 10, fontWeight: 700, cursor: 'pointer', fontFamily: 'var(--font-mono)', opacity: !newName.trim() ? 0.4 : 1 }}
              >
                CREATE
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Experiment grid */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
        {experiments.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#1e2d3d', fontFamily: 'var(--font-mono)', fontSize: 11, marginTop: 60 }}>
            NO EXPERIMENTS YET
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
            {experiments.map(exp => (
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

function ExperimentCard({ exp, onClick }: { exp: Experiment; onClick: () => void }) {
  const color = STATUS_COLORS[exp.status] ?? '#64748b'
  return (
    <div
      onClick={onClick}
      style={{
        background: 'rgba(17,30,53,0.75)', border: '1px solid rgba(100,140,200,0.09)',
        borderRadius: 8, padding: '14px 16px', cursor: 'pointer',
        transition: 'border-color 0.15s',
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = 'rgba(100,140,200,0.25)')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'rgba(100,140,200,0.09)')}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#f1f5f9', lineHeight: 1.3 }}>{exp.name}</div>
        <span style={{
          fontSize: 7, fontWeight: 700, fontFamily: 'var(--font-mono)',
          color, background: `${color}18`, border: `1px solid ${color}33`,
          borderRadius: 2, padding: '1px 5px', flexShrink: 0, marginLeft: 8,
        }}>
          {exp.status.toUpperCase()}
        </span>
      </div>
      {exp.hypothesis && (
        <p style={{ fontSize: 10, color: '#64748b', margin: '0 0 8px', lineHeight: 1.5, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
          {exp.hypothesis}
        </p>
      )}
      {exp.tags.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
          {exp.tags.map(tag => (
            <span key={tag} style={{ fontSize: 7, color: '#475569', background: 'rgba(100,140,200,0.06)', border: '1px solid rgba(100,140,200,0.1)', borderRadius: 2, padding: '1px 4px' }}>
              {tag}
            </span>
          ))}
        </div>
      )}
      {exp.deadline && (
        <div style={{ fontSize: 9, color: '#475569', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
          DEADLINE: {exp.deadline}
        </div>
      )}
    </div>
  )
}
