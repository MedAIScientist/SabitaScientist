import React, { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  api, EXPERIMENT_ASSET_ROLES, EXPERIMENT_ASSET_TYPE_LABELS,
  ExperimentAsset, ExperimentAssetRole, ExperimentAssetType,
} from '../../api'

const ROLE_COLORS: Record<ExperimentAssetRole, string> = {
  input: '#6366f1',
  processing: '#f59e0b',
  output: '#10b981',
  reference: '#6b7280',
}

const ROLE_HINT: Record<ExperimentAssetRole, string> = {
  input: 'the cohort or data that went in',
  processing: 'how it was transformed',
  output: 'what the experiment produced',
  reference: 'supporting material',
}

const ASSET_TYPES: ExperimentAssetType[] = [
  'dataset', 'pipeline_run', 'cvat_project', 'webknossos_dataset', 'sandbox',
]

const inputStyle: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box', padding: '7px 10px',
  background: 'var(--surface-input)', border: '1px solid var(--border)',
  borderRadius: 6, color: 'var(--text)', fontSize: 15, outline: 'none',
}

const smallBtn: React.CSSProperties = {
  cursor: 'pointer', padding: '4px 9px', borderRadius: 4,
  background: 'transparent', border: '1px solid var(--border)',
  color: 'var(--text-muted)', fontSize: 13,
  fontFamily: 'var(--font-mono)', fontWeight: 700,
}

/**
 * The experiment's data lineage: which imaging cohort it consumed, which
 * de-identification run processed it, and which annotations or segmentations it
 * produced. Assets stay owned by their project/lab; this only records the link.
 */
export function ExperimentDataTab({ projectId, experimentId }: {
  projectId: string; experimentId: string
}) {
  const qc = useQueryClient()
  const [assetType, setAssetType] = useState<ExperimentAssetType>('dataset')
  const [assetId, setAssetId] = useState('')
  const [role, setRole] = useState<ExperimentAssetRole>('input')
  const [error, setError] = useState<string | null>(null)

  const { data: assets = [], isLoading } = useQuery({
    queryKey: ['experiment-assets', projectId, experimentId],
    queryFn: () => api.listExperimentAssets(projectId, experimentId),
  })

  // Only the selected kind is fetched, so opening the tab costs one request.
  const { data: options = [] } = useQuery({
    queryKey: ['asset-options', projectId, assetType],
    queryFn: async (): Promise<{ id: string; label: string; detail: string }[]> => {
      if (assetType === 'dataset') {
        const rows = await api.listDatasets()
        return rows.map(d => ({ id: d.id, label: d.name, detail: d.status }))
      }
      if (assetType === 'pipeline_run') {
        const rows = await api.listProjectDeidRuns(projectId)
        return rows.map(r => ({
          id: r.id,
          label: `Run ${r.id.slice(0, 8)}`,
          detail: `${r.status} · ${r.records_processed ?? 0} records`,
        }))
      }
      if (assetType === 'cvat_project') {
        const rows = await api.listProjectCvat(projectId)
        return rows.map(c => ({
          id: c.id, label: c.name, detail: `${c.status} · ${c.num_images} images`,
        }))
      }
      if (assetType === 'webknossos_dataset') {
        const rows = await api.listProjectWebknossos(projectId)
        return rows.map(w => ({
          id: w.id, label: w.name, detail: `${w.status} · ${w.num_volumes} volumes`,
        }))
      }
      const rows = await api.listProjectSandboxes(projectId)
      return rows.map(s => ({ id: s.id, label: s.name, detail: s.status }))
    },
  })

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['experiment-assets', projectId, experimentId] })
    qc.invalidateQueries({ queryKey: ['experiments', projectId] })
  }

  const link = useMutation({
    mutationFn: () => api.linkExperimentAsset(projectId, experimentId, {
      asset_type: assetType, asset_id: assetId, role,
    }),
    onSuccess: () => { refresh(); setAssetId(''); setError(null) },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : 'Could not link the asset'),
  })

  const unlink = useMutation({
    mutationFn: (a: ExperimentAsset) =>
      api.unlinkExperimentAsset(projectId, experimentId, a.asset_type, a.asset_id),
    onSuccess: refresh,
  })

  const byRole = (r: ExperimentAssetRole) => assets.filter(a => a.role === r)

  return (
    <div>
      <div style={{
        fontSize: 15, color: 'var(--text-dim)', marginBottom: 12, lineHeight: 1.5,
      }}>
        Trace this experiment to the data it consumed and the imaging artefacts it
        produced. Links point at assets owned by the project — nothing is copied.
      </div>

      {error && (
        <div style={{
          padding: '7px 10px', marginBottom: 10, background: 'rgba(244,63,94,0.08)',
          border: '1px solid rgba(244,63,94,0.2)', borderRadius: 5,
          color: '#f43f5e', fontSize: 16,
        }}>{error}</div>
      )}

      {/* Link builder */}
      <div style={{
        background: 'var(--surface-2)', border: '1px solid var(--border)',
        borderRadius: 6, padding: 10, marginBottom: 14,
      }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
          <select
            value={assetType}
            onChange={e => { setAssetType(e.target.value as ExperimentAssetType); setAssetId('') }}
            style={inputStyle}
          >
            {ASSET_TYPES.map(t => (
              <option key={t} value={t}>{EXPERIMENT_ASSET_TYPE_LABELS[t]}</option>
            ))}
          </select>
          <select
            value={role}
            onChange={e => setRole(e.target.value as ExperimentAssetRole)}
            style={inputStyle}
          >
            {EXPERIMENT_ASSET_ROLES.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <select value={assetId} onChange={e => setAssetId(e.target.value)} style={inputStyle}>
          <option value="">— pick one —</option>
          {options.map(o => (
            <option key={o.id} value={o.id}>{o.label} ({o.detail})</option>
          ))}
        </select>
        <button
          onClick={() => link.mutate()}
          disabled={!assetId || link.isPending}
          style={{
            width: '100%', marginTop: 8, padding: '7px 0', borderRadius: 5,
            cursor: !assetId ? 'default' : 'pointer', border: 'none',
            background: !assetId || link.isPending ? 'rgba(var(--accent-rgb),0.35)' : 'var(--accent)',
            color: '#fff', fontSize: 15, fontWeight: 700, fontFamily: 'var(--font-mono)',
          }}
        >{link.isPending ? 'Linking…' : `LINK AS ${role.toUpperCase()}`}</button>
        <div style={{ fontSize: 13, color: 'var(--text-3)', marginTop: 5 }}>
          {ROLE_HINT[role]}
        </div>
      </div>

      {isLoading ? (
        <Muted>Loading…</Muted>
      ) : assets.length === 0 ? (
        <Muted>Nothing linked yet.</Muted>
      ) : (
        EXPERIMENT_ASSET_ROLES.map(r => {
          const rows = byRole(r)
          if (rows.length === 0) return null
          return (
            <div key={r} style={{ marginBottom: 12 }}>
              <div style={{
                fontSize: 13, fontWeight: 700, letterSpacing: '0.04em',
                fontFamily: 'var(--font-mono)', color: ROLE_COLORS[r], marginBottom: 5,
              }}>{r.toUpperCase()}</div>
              {rows.map(a => (
                <div key={`${a.asset_type}:${a.asset_id}`} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  background: 'var(--surface-2)', border: '1px solid var(--border)',
                  borderLeft: `2px solid ${ROLE_COLORS[r]}`,
                  borderRadius: '0 5px 5px 0', padding: '7px 9px', marginBottom: 5,
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 15, color: 'var(--text)' }}>
                      {a.label ?? a.asset_id.slice(0, 8)}
                    </div>
                    <div style={{
                      fontSize: 12, color: 'var(--text-3)', fontFamily: 'var(--font-mono)',
                      marginTop: 1,
                    }}>
                      {EXPERIMENT_ASSET_TYPE_LABELS[a.asset_type]}
                      {a.detail ? ` · ${a.detail}` : ''}
                    </div>
                  </div>
                  <button
                    style={{ ...smallBtn, borderColor: 'rgba(244,63,94,0.3)', color: '#f43f5e' }}
                    onClick={() => unlink.mutate(a)}
                  >✕</button>
                </div>
              ))}
            </div>
          )
        })
      )}
    </div>
  )
}

function Muted({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      padding: '16px 0', color: 'var(--text-dim)',
      fontFamily: 'var(--font-mono)', fontSize: 15,
    }}>{children}</div>
  )
}
