import React, { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Publication_, Version, Review, Pipeline } from '../api'

const STATUS_OPTIONS = ['draft', 'submitted', 'reviewing', 'accepted', 'published', 'rejected']
const STATUS_COLORS: Record<string, string> = {
  draft: '#6b7280', submitted: '#6366f1', reviewing: '#f59e0b',
  accepted: '#10b981', published: '#059669', rejected: '#f43f5e',
}

type AITab = 'section' | 'revise' | 'review_response' | null

const SECTIONS = [
  { id: 'abstract', label: 'Abstract' },
  { id: 'introduction', label: 'Introduction' },
  { id: 'methods', label: 'Methods' },
  { id: 'results', label: 'Results' },
  { id: 'discussion', label: 'Discussion' },
  { id: 'conclusion', label: 'Conclusion' },
]

const STYLES = [
  { id: 'standard', label: 'Standard' },
  { id: 'concise', label: 'Concise' },
  { id: 'detailed', label: 'Detailed' },
  { id: 'lay', label: 'Lay Summary' },
]

export function PublicationDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState('')
  const [editVenue, setEditVenue] = useState('')
  const [editAbstract, setEditAbstract] = useState('')
  const [editDoi, setEditDoi] = useState('')
  const [showNewVersion, setShowNewVersion] = useState(false)
  const [versionNotes, setVersionNotes] = useState('')
  const [showNewReview, setShowNewReview] = useState(false)
  const [reviewerName, setReviewerName] = useState('')
  const [reviewComments, setReviewComments] = useState('')
  const [reviewDecision, setReviewDecision] = useState('')

  // AI paper composer state
  const [aiTab, setAiTab] = useState<AITab>(null)
  const [aiSection, setAiSection] = useState('abstract')
  const [aiStyle, setAiStyle] = useState('standard')
  const [reviseInstructions, setReviseInstructions] = useState('')
  const [reviewerComments, setReviewerComments] = useState('')

  const { data: pub, isLoading } = useQuery({
    queryKey: ['publication', id],
    queryFn: () => api.getPublication(id!),
    enabled: Boolean(id),
  })

  const { data: versions = [] } = useQuery({
    queryKey: ['versions', id],
    queryFn: () => api.listVersions(id!),
    enabled: Boolean(id),
  })

  const { data: reviews = [] } = useQuery({
    queryKey: ['reviews', id],
    queryFn: () => api.listReviews(id!),
    enabled: Boolean(id),
  })

  const { data: projectExps = [] } = useQuery({
    queryKey: ['experiments', pub?.project_id],
    queryFn: () => pub?.project_id ? api.listExperiments(pub.project_id) : [],
    enabled: Boolean(pub?.project_id),
  })

  const { data: pipeline } = useQuery({
    queryKey: ['pipeline', id],
    queryFn: () => api.getPublicationPipeline(id!),
    enabled: Boolean(id),
  })

  const updateMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.updatePublication(id!, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['publication', id] }); setEditing(false) },
  })

  const submitMutation = useMutation({
    mutationFn: () => api.submitPublication(id!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['publication', id] }),
  })

  const versionMutation = useMutation({
    mutationFn: () => api.createVersion(id!, versionNotes || undefined),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['versions', id] }); setShowNewVersion(false); setVersionNotes('') },
  })

  const reviewMutation = useMutation({
    mutationFn: () => api.createReview(id!, {
      reviewer_name: reviewerName || undefined,
      comments: reviewComments || undefined,
      decision: reviewDecision || undefined,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['reviews', id] }); setShowNewReview(false); setReviewerName(''); setReviewComments(''); setReviewDecision('') },
  })

  const draftSectionMutation = useMutation({
    mutationFn: () => api.draftSection(id!, aiSection, aiStyle),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['versions', id] })
      setAiTab(null)
    },
  })

  const draftFromExpMutation = useMutation({
    mutationFn: ({ expId, section }: { expId: string; section: string }) =>
      api.draftFromExperiment(pub!.project_id!, expId, section, aiStyle),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['versions', id] })
    },
  })

  const reviseMutation = useMutation({
    mutationFn: () => api.revisePublication(id!, reviseInstructions, pub?.abstract || undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['publication', id] })
      qc.invalidateQueries({ queryKey: ['versions', id] })
      setAiTab(null); setReviseInstructions('')
    },
  })

  const respondMutation = useMutation({
    mutationFn: () => api.respondToReviewers(id!, reviewerComments),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['versions', id] })
      setAiTab(null); setReviewerComments('')
    },
  })

  const linkExpMutation = useMutation({
    mutationFn: ({ expId, section }: { expId: string; section?: string }) =>
      api.linkExperimentToPub(id!, expId, section),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pipeline', id] }),
  })

  if (isLoading || !pub) return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', padding: 40, fontFamily: 'var(--font-mono)', fontSize: 19 }}>
      LOADING…
    </div>
  )

  const inputStyle: React.CSSProperties = {
    padding: '9px 12px', background: 'var(--surface-input)',
    border: '1px solid var(--border)', borderRadius: 7,
    color: 'var(--text)', fontSize: 22, outline: 'none', width: '100%', boxSizing: 'border-box',
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <div style={{ maxWidth: 860, margin: '0 auto', padding: '32px 28px', display: 'flex', gap: 24 }}>
        {/* Main content */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Header */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
              <div style={{ flex: 1, marginRight: 20 }}>
                {editing ? (
                  <input value={editTitle} onChange={e => setEditTitle(e.target.value)} style={inputStyle} />
                ) : (
                  <h1 style={{ margin: 0, fontSize: 26, fontWeight: 600, color: 'var(--text-heading)', lineHeight: 1.3 }}>{pub.title}</h1>
                )}
                <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
                  <span style={{
                    fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)',
                    color: STATUS_COLORS[pub.status],
                    background: `${STATUS_COLORS[pub.status]}14`,
                    border: `1px solid ${STATUS_COLORS[pub.status]}30`,
                    borderRadius: 4, padding: '1px 7px',
                  }}>{pub.status.toUpperCase()}</span>
                  <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', padding: '1px 0' }}>
                    {pub.venue_type.toUpperCase()}
                  </span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                {pub.status === 'draft' && (
                  <button onClick={() => submitMutation.mutate()} style={{
                    cursor: 'pointer', padding: '6px 12px',
                    background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.3)',
                    borderRadius: 6, color: '#6366f1', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
                  }}>SUBMIT</button>
                )}
                <button onClick={() => {
                  if (!editing) { setEditTitle(pub.title); setEditVenue(pub.venue || ''); setEditAbstract(pub.abstract || ''); setEditDoi(pub.doi || '') }
                  setEditing(e => !e)
                }} style={{
                  cursor: 'pointer', padding: '6px 12px',
                  background: 'rgba(255,128,21,0.1)', border: '1px solid rgba(255,128,21,0.3)',
                  borderRadius: 6, color: '#ff8015', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
                }}>{editing ? 'CANCEL' : 'EDIT'}</button>
              </div>
            </div>
          </div>

          {/* Edit form */}
          {editing && (
            <div style={{ background: 'var(--surface-card)', border: '1px solid rgba(255,128,21,0.2)', borderRadius: 10, padding: 20, marginBottom: 20 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <div><label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>VENUE</label>
                  <input value={editVenue} onChange={e => setEditVenue(e.target.value)} style={inputStyle} /></div>
                <div><label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>DOI</label>
                  <input value={editDoi} onChange={e => setEditDoi(e.target.value)} placeholder="10.xxxx/xxxxx" style={inputStyle} /></div>
              </div>
              <div style={{ marginBottom: 12 }}><label style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>ABSTRACT</label>
                <textarea value={editAbstract} onChange={e => setEditAbstract(e.target.value)} rows={4} style={{ ...inputStyle, resize: 'vertical' }} /></div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
                {STATUS_OPTIONS.map(s => (
                  <button key={s} onClick={() => updateMutation.mutate({ status: s })} style={{
                    cursor: 'pointer', padding: '3px 8px', fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 700,
                    background: pub.status === s ? `${STATUS_COLORS[s]}20` : 'transparent',
                    border: `1px solid ${STATUS_COLORS[s]}40`, borderRadius: 3, color: STATUS_COLORS[s],
                  }}>{s.toUpperCase()}</button>
                ))}
              </div>
              <button onClick={() => updateMutation.mutate({ title: editTitle, venue: editVenue || null, abstract: editAbstract || null, doi: editDoi || null })}
                style={{ padding: '8px 20px', cursor: 'pointer', background: '#ff8015', color: '#06091a', border: 'none', borderRadius: 6, fontSize: 17, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                SAVE
              </button>
            </div>
          )}

          {/* Abstract */}
          {!editing && pub.abstract && (
            <div style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: 18, marginBottom: 20 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginBottom: 6 }}>ABSTRACT</div>
              <p style={{ margin: 0, fontSize: 18, color: 'var(--text-2)', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{pub.abstract}</p>
            </div>
          )}

          {!editing && (pub.venue || pub.doi || pub.project_name) && (
            <div style={{ display: 'flex', gap: 20, marginBottom: 20, fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
              {pub.project_name && <span>Project: {pub.project_name}</span>}
              {pub.venue && <span>Venue: {pub.venue}</span>}
              {pub.doi && <span>DOI: {pub.doi}</span>}
            </div>
          )}

          {/* Pipeline visualization */}
          {pipeline && pipeline.pipeline_stages && (
            <div style={{ background: 'var(--surface-card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 20px', marginBottom: 20 }}>
              <div style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)', marginBottom: 12, letterSpacing: '0.06em' }}>
                📋 PUBLICATION PIPELINE
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                {pipeline.pipeline_stages.map((stage, i) => {
                  const stageColors: Record<string, string> = {
                    done: '#10b981', active: '#f59e0b', pending: '#6b7280', none: '#374151',
                  }
                  const stageLabels: Record<string, string> = {
                    project: '📁 Project', experiments: '🔬 Experiments', draft: '✍ Draft',
                    submitted: '📤 Submitted', review: '👁 Review', accepted: '✅ Accepted',
                    published: '📰 Published',
                  }
                  const color = stageColors[stage.status] || '#6b7280'
                  return (
                    <React.Fragment key={stage.stage}>
                      <div style={{
                        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
                      }}>
                        <div style={{
                          width: 32, height: 32, borderRadius: '50%',
                          background: `${color}20`, border: `2px solid ${color}`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 14, fontWeight: 700, color, fontFamily: 'var(--font-mono)',
                        }}>
                          {stage.status === 'done' ? '✓' : stage.status === 'active' ? '●' : stage.status === 'none' ? '–' : '○'}
                        </div>
                        <span style={{ fontSize: 12, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', textAlign: 'center', maxWidth: 80 }}>
                          {stageLabels[stage.stage] || stage.stage}
                        </span>
                      </div>
                      {i < pipeline.pipeline_stages.length - 1 && (
                        <div style={{
                          flex: 1, minWidth: 16, height: 2,
                          background: stage.status === 'done' ? '#10b981' : 'var(--border)',
                          marginBottom: 20,
                        }} />
                      )}
                    </React.Fragment>
                  )
                })}
              </div>
            </div>
          )}

          {/* Linked experiments */}
          {pipeline && pipeline.linked_experiments && pipeline.linked_experiments.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)', marginBottom: 8 }}>
                🔗 LINKED EXPERIMENTS ({pipeline.linked_experiments.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {pipeline.linked_experiments.map(exp => (
                  <div key={exp.experiment_id} style={{
                    background: 'var(--surface-card)', border: '1px solid var(--border)',
                    borderRadius: 8, padding: '10px 14px',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  }}>
                    <div>
                      <span style={{ fontSize: 17, fontWeight: 500, color: 'var(--text-heading)' }}>{exp.name}</span>
                      {exp.section && <span style={{ fontSize: 14, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginLeft: 8 }}>({exp.section})</span>}
                    </div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <span style={{
                        fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 700,
                        color: exp.status === 'completed' ? '#10b981' : exp.status === 'running' ? '#ff8015' : '#f59e0b',
                        padding: '1px 6px', borderRadius: 3, background: 'var(--surface-input)',
                      }}>{exp.status.toUpperCase()}</span>
                      <span style={{ fontSize: 14, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                        {exp.entry_count} entries
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI Paper Composer */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
              {([
                { key: 'section' as const, label: '✍ Draft Section', color: '#6366f1' },
                { key: 'revise' as const, label: '✏ Revise', color: '#f59e0b' },
                { key: 'review_response' as const, label: '📝 Reviewer Response', color: '#ec4899' },
              ]).map(btn => (
                <button
                  key={btn.key}
                  onClick={() => setAiTab(aiTab === btn.key ? null : btn.key)}
                  style={{
                    cursor: 'pointer', padding: '5px 12px', fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)',
                    background: aiTab === btn.key ? `${btn.color}18` : `${btn.color}08`,
                    border: `1px solid ${btn.color}30`, borderRadius: 5, color: btn.color,
                    letterSpacing: '0.06em', transition: 'background 0.12s',
                  }}
                >{btn.label}</button>
              ))}
            </div>

            {/* Section drafting panel */}
            {aiTab === 'section' && (
              <div style={{ background: 'var(--surface-card)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 10, padding: 18, marginBottom: 12 }}>
                <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#6366f1', marginBottom: 12 }}>Draft a Section</div>
                <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-dim)', marginBottom: 3, fontFamily: 'var(--font-mono)' }}>SECTION</div>
                    <select value={aiSection} onChange={e => setAiSection(e.target.value)} style={inputStyle}>
                      {SECTIONS.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
                    </select>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-dim)', marginBottom: 3, fontFamily: 'var(--font-mono)' }}>STYLE</div>
                    <select value={aiStyle} onChange={e => setAiStyle(e.target.value)} style={inputStyle}>
                      {STYLES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
                    </select>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'end' }}>
                    <button onClick={() => draftSectionMutation.mutate()} disabled={draftSectionMutation.isPending}
                      style={{
                        padding: '8px 16px', cursor: 'pointer', height: 44,
                        background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.28)',
                        borderRadius: 6, color: '#6366f1', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
                        whiteSpace: 'nowrap',
                      }}
                    >{draftSectionMutation.isPending ? '…' : 'GENERATE'}</button>
                  </div>
                </div>

                {/* Draft from experiment */}
                {pub.project_id && projectExps.length > 0 && (
                  <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 10, marginTop: 10 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-dim)', marginBottom: 6, fontFamily: 'var(--font-mono)' }}>OR DRAFT FROM EXPERIMENT</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {projectExps.map(exp => (
                        <div key={exp.id} style={{
                          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                          background: 'var(--surface-input)', borderRadius: 6, padding: '8px 12px',
                        }}>
                          <span style={{ fontSize: 16, color: 'var(--text-2)' }}>{exp.name}</span>
                          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                            {['results', 'methods', 'discussion'].map(sec => (
                              <button key={sec}
                                onClick={() => draftFromExpMutation.mutate({ expId: exp.id, section: sec })}
                                style={{
                                  cursor: 'pointer', padding: '2px 7px', fontSize: 12, fontFamily: 'var(--font-mono)',
                                  background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)',
                                  borderRadius: 3, color: '#6366f1', fontWeight: 700,
                                }}
                              >{sec}</button>
                            ))}
                            <button
                              onClick={async () => {
                                try { await api.linkExperimentToPub(id!, exp.id); qc.invalidateQueries({ queryKey: ['pipeline', id] }) }
                                catch (e) { alert(e instanceof Error ? e.message : 'Failed') }
                              }}
                              style={{
                                cursor: 'pointer', padding: '2px 7px', fontSize: 12, fontFamily: 'var(--font-mono)',
                                background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)',
                                borderRadius: 3, color: '#10b981', fontWeight: 700,
                              }}
                            >🔗 link</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Revise panel */}
            {aiTab === 'revise' && (
              <div style={{ background: 'var(--surface-card)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 10, padding: 18, marginBottom: 12 }}>
                <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#f59e0b', marginBottom: 8 }}>Revise Text</div>
                <textarea value={reviseInstructions} onChange={e => setReviseInstructions(e.target.value)}
                  placeholder="e.g. Make this more concise. Improve clarity. Add more context to the results. Improve academic tone."
                  rows={3} style={{ ...inputStyle, marginBottom: 10, resize: 'vertical' }} />
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => reviseMutation.mutate()} disabled={reviseMutation.isPending || !reviseInstructions.trim()}
                    style={{
                      padding: '8px 16px', cursor: 'pointer',
                      background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.28)',
                      borderRadius: 6, color: '#f59e0b', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
                    }}
                  >{reviseMutation.isPending ? '…' : 'REVISE'}</button>
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 6 }}>
                  {pub.abstract ? `Will revise current abstract (${pub.abstract.length} chars)` : 'No abstract to revise — add one first.'}
                </div>
              </div>
            )}

            {/* Reviewer response panel */}
            {aiTab === 'review_response' && (
              <div style={{ background: 'var(--surface-card)', border: '1px solid rgba(236,72,153,0.2)', borderRadius: 10, padding: 18, marginBottom: 12 }}>
                <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#ec4899', marginBottom: 8 }}>Generate Reviewer Response</div>
                <textarea value={reviewerComments} onChange={e => setReviewerComments(e.target.value)}
                  placeholder="Paste the full reviewer comments here. The AI will generate a point-by-point response letter."
                  rows={5} style={{ ...inputStyle, marginBottom: 10, resize: 'vertical', fontSize: 18 }} />
                <button onClick={() => respondMutation.mutate()} disabled={respondMutation.isPending || !reviewerComments.trim()}
                  style={{
                    padding: '8px 16px', cursor: 'pointer',
                    background: 'rgba(236,72,153,0.12)', border: '1px solid rgba(236,72,153,0.28)',
                    borderRadius: 6, color: '#ec4899', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
                  }}
                >{respondMutation.isPending ? '…' : 'GENERATE RESPONSE'}</button>
              </div>
            )}
          </div>

          {/* Versions */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <h3 style={{ margin: 0, fontSize: 20, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>
              Versions ({versions.length})
            </h3>
            <button onClick={() => setShowNewVersion(true)} style={{
              cursor: 'pointer', padding: '4px 10px',
              background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)',
              borderRadius: 5, color: '#10b981', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
            }}>+ NEW</button>
          </div>

          {showNewVersion && (
            <div style={{ background: 'var(--surface-card)', border: '1px solid rgba(16,185,129,0.2)', borderRadius: 8, padding: 14, marginBottom: 10 }}>
              <textarea value={versionNotes} onChange={e => setVersionNotes(e.target.value)} placeholder="Version notes…" rows={2}
                style={{ ...inputStyle, marginBottom: 6, resize: 'vertical', fontSize: 18 }} />
              <div style={{ display: 'flex', gap: 6 }}>
                <button onClick={() => versionMutation.mutate()} style={{ padding: '5px 14px', cursor: 'pointer', background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.28)', borderRadius: 5, color: '#10b981', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>CREATE</button>
                <button onClick={() => setShowNewVersion(false)} style={{ padding: '5px 10px', cursor: 'pointer', background: 'transparent', border: '1px solid var(--border)', borderRadius: 5, color: 'var(--text-muted)', fontSize: 15 }}>CANCEL</button>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 28 }}>
            {versions.map(v => (
              <div key={v.id} style={{
                background: 'var(--surface-card)', border: '1px solid var(--border)',
                borderRadius: 7, padding: '10px 14px', display: 'flex', justifyContent: 'space-between',
              }}>
                <div>
                  <span style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', fontSize: 16 }}>v{v.version}</span>
                  {v.notes && <span style={{ color: 'var(--text-2)', marginLeft: 10, fontSize: 16 }}>{v.notes}</span>}
                </div>
                <span style={{ fontSize: 13, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                  {new Date(v.created_at).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>

          {/* Reviews */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <h3 style={{ margin: 0, fontSize: 20, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>
              Reviews ({reviews.length})
            </h3>
            <button onClick={() => setShowNewReview(true)} style={{
              cursor: 'pointer', padding: '4px 10px',
              background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.3)',
              borderRadius: 5, color: '#6366f1', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
            }}>+ ADD</button>
          </div>

          {showNewReview && (
            <div style={{ background: 'var(--surface-card)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 8, padding: 14, marginBottom: 10 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 6 }}>
                <div><label style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>REVIEWER</label>
                  <input value={reviewerName} onChange={e => setReviewerName(e.target.value)} style={inputStyle} /></div>
                <div><label style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>DECISION</label>
                  <select value={reviewDecision} onChange={e => setReviewDecision(e.target.value)} style={inputStyle}>
                    <option value="">—</option>
                    <option value="accept">Accept</option>
                    <option value="minor_revision">Minor Revision</option>
                    <option value="major_revision">Major Revision</option>
                    <option value="reject">Reject</option>
                  </select></div>
              </div>
              <textarea value={reviewComments} onChange={e => setReviewComments(e.target.value)} placeholder="Comments…" rows={3}
                style={{ ...inputStyle, marginBottom: 6, resize: 'vertical' }} />
              <div style={{ display: 'flex', gap: 6 }}>
                <button onClick={() => reviewMutation.mutate()} style={{ padding: '5px 14px', cursor: 'pointer', background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.28)', borderRadius: 5, color: '#6366f1', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>ADD REVIEW</button>
                <button onClick={() => setShowNewReview(false)} style={{ padding: '5px 10px', cursor: 'pointer', background: 'transparent', border: '1px solid var(--border)', borderRadius: 5, color: 'var(--text-muted)', fontSize: 15 }}>CANCEL</button>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {reviews.map(r => (
              <div key={r.id} style={{
                background: 'var(--surface-card)', border: '1px solid var(--border)',
                borderRadius: 7, padding: '12px 14px',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <span style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', fontSize: 16 }}>Round {r.round}</span>
                    {r.reviewer_name && <span style={{ color: 'var(--text-dim)' }}>— {r.reviewer_name}</span>}
                  </div>
                  {r.decision && (
                    <span style={{
                      fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)',
                      color: STATUS_COLORS[r.decision === 'accept' ? 'accepted' : r.decision === 'reject' ? 'rejected' : 'reviewing'],
                      padding: '1px 5px', borderRadius: 3, background: 'var(--surface-input)',
                    }}>{r.decision.replace('_', ' ').toUpperCase()}</span>
                  )}
                </div>
                {r.comments && <p style={{ margin: '0 0 4px', fontSize: 17, color: 'var(--text-2)', lineHeight: 1.5 }}>{r.comments}</p>}
                <div style={{ fontSize: 13, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                  {new Date(r.created_at).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
