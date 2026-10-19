import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ProjectAttachment } from '../api'
import { ProjectHeader } from '../components/ProjectHeader'
import { fileIcon, formatBytes, isViewable, openAttachmentFile } from '../attachments'

type Filter = 'all' | 'task' | 'entry'

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'all', label: 'All files' },
  { value: 'task', label: 'Task files' },
  { value: 'entry', label: 'Experiment files' },
]

/**
 * Every file in the project, wherever it was attached.
 *
 * Attaching a file to a task or an experiment entry puts it next to the work it
 * belongs to, which is right. Finding it again should not require remembering
 * which task that was, so the project has one list of its files.
 */
export function ProjectFilesPage() {
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [filter, setFilter] = useState<Filter>('all')
  const [opening, setOpening] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.getProject(projectId!),
    enabled: Boolean(projectId),
  })

  const { data: files = [], isLoading } = useQuery({
    queryKey: ['project-files', projectId, filter],
    queryFn: () => api.listProjectAttachments(projectId!, filter === 'all' ? undefined : filter),
    enabled: Boolean(projectId),
  })

  const remove = useMutation({
    mutationFn: (attachmentId: string) => api.deleteAttachment(attachmentId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['project-files', projectId] }),
    onError: (err: Error) => setError(err.message),
  })

  async function open(file: ProjectAttachment) {
    setError(null)
    setOpening(file.id)
    try {
      await openAttachmentFile(file)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setOpening(null)
    }
  }

  function ownerLink(file: ProjectAttachment): { path: string; label: string } {
    if (file.owner_kind === 'task') {
      return { path: `/projects/${projectId}`, label: `Task · ${file.owner_title}` }
    }
    return {
      path: `/projects/${projectId}/experiments`,
      label: `Experiment · ${file.owner_title}`,
    }
  }

  const totalBytes = files.reduce((sum, file) => sum + file.size_bytes, 0)

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: '0 auto' }}>
      <ProjectHeader projectId={projectId!} name={project?.name} />

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', margin: '18px 0 14px', flexWrap: 'wrap' }}>
        {FILTERS.map(f => (
          <button
            key={f.value}
            className={filter === f.value ? 'btn btn-primary' : 'btn'}
            aria-pressed={filter === f.value}
            onClick={() => setFilter(f.value)}
            style={{ fontSize: 13 }}
          >
            {f.label}
          </button>
        ))}
        <span style={{ marginLeft: 'auto', fontSize: 13, color: 'var(--text-3)' }}>
          {files.length} file{files.length === 1 ? '' : 's'} · {formatBytes(totalBytes)}
        </span>
      </div>

      {error && (
        <div style={{ padding: '8px 12px', marginBottom: 12, borderRadius: 6, background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.2)', color: '#f43f5e', fontSize: 14 }} role="status">
          {error}
        </div>
      )}

      {isLoading ? (
        <p style={{ color: 'var(--text-2)' }}>Loading files…</p>
      ) : files.length === 0 ? (
        <div style={{ border: '1px dashed var(--border)', borderRadius: 8, padding: 28, textAlign: 'center' }}>
          <p style={{ color: 'var(--text-2)', margin: 0 }}>
            No files yet. Attach one in a task’s <strong>FILES</strong> tab, or to an experiment entry.
          </p>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--text-3)', fontSize: 12 }}>
                <th style={{ padding: '10px 12px', fontWeight: 600 }}>FILE</th>
                <th style={{ padding: '10px 12px', fontWeight: 600 }}>ATTACHED TO</th>
                <th style={{ padding: '10px 12px', fontWeight: 600 }}>SIZE</th>
                <th style={{ padding: '10px 12px', fontWeight: 600 }}>BY</th>
                <th style={{ padding: '10px 12px', fontWeight: 600 }}>WHEN</th>
                <th style={{ padding: '10px 12px' }} />
              </tr>
            </thead>
            <tbody>
              {files.map(file => {
                const owner = ownerLink(file)
                return (
                  <tr key={file.id} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '10px 12px' }}>
                      <button
                        onClick={() => open(file)}
                        disabled={opening === file.id}
                        title={isViewable(file.content_type) ? 'Open' : 'Save'}
                        style={{
                          background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                          color: 'var(--accent)', fontSize: 14, textAlign: 'left',
                        }}
                      >
                        <span style={{ marginRight: 6 }}>{fileIcon(file.content_type)}</span>
                        {opening === file.id ? 'Opening…' : file.filename}
                      </button>
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <a
                        href={owner.path}
                        onClick={e => { e.preventDefault(); navigate(owner.path) }}
                        style={{ color: 'var(--text-2)', fontSize: 13 }}
                      >
                        {owner.label}
                      </a>
                    </td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-3)', whiteSpace: 'nowrap' }}>
                      {formatBytes(file.size_bytes)}
                    </td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-3)' }}>
                      {file.uploader_name ?? '—'}
                    </td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-3)', whiteSpace: 'nowrap' }}>
                      {file.created_at.slice(0, 10)}
                    </td>
                    <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                      <button
                        onClick={() => remove.mutate(file.id)}
                        disabled={remove.isPending}
                        title="Delete file"
                        style={{ background: 'none', border: 'none', color: '#f43f5e', cursor: 'pointer', fontSize: 14 }}
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
