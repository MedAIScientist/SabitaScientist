import { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Attachment } from '../api'
import { fileIcon, formatBytes, isViewable, openAttachmentFile } from '../attachments'

const MAX_MB = 50
const ALLOWED_TYPES = [
  'image/', 'text/', 'application/pdf', 'application/json',
  'application/zip', 'application/gzip', 'application/x-tar', 'application/octet-stream',
]

function isAllowedType(type: string) {
  return ALLOWED_TYPES.some(t => type.startsWith(t))
}

/**
 * What the files belong to. An attachment has exactly one owner, so the component
 * asks for the owner rather than a pile of optional ids.
 */
export type AttachmentTarget =
  | { kind: 'entry'; projectId: string; expId: string; entryId: string }
  | { kind: 'task'; projectId: string; taskId: string }

interface Props {
  target: AttachmentTarget
  accent: string
}

export function AttachmentList({ target, accent }: Props) {
  const qc = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [opening, setOpening] = useState<string | null>(null)

  const ownerId = target.kind === 'entry' ? target.entryId : target.taskId
  const queryKey = ['attachments', target.kind, ownerId]

  const { data: attachments = [] } = useQuery<Attachment[]>({
    queryKey,
    queryFn: () =>
      target.kind === 'entry'
        ? api.listAttachments(target.projectId, target.expId, target.entryId)
        : api.listTaskAttachments(target.projectId, target.taskId),
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) =>
      target.kind === 'entry'
        ? api.uploadAttachment(target.projectId, target.expId, target.entryId, file)
        : api.uploadTaskAttachment(target.projectId, target.taskId, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey })
      setError(null)
    },
    onError: (err: Error) => setError(err.message),
  })

  const deleteMutation = useMutation({
    mutationFn: (attachmentId: string) => api.deleteAttachment(attachmentId),
    onSuccess: () => qc.invalidateQueries({ queryKey }),
    onError: (err: Error) => setError(err.message),
  })

  /** Open the file the way its type deserves: view it, or save it. */
  async function openAttachment(a: Attachment) {
    setError(null)
    setOpening(a.id)
    try {
      await openAttachmentFile(a)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setOpening(null)
    }
  }

  function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return
    const file = files[0]
    if (!isAllowedType(file.type || '')) {
      setError(`File type "${file.type || 'unknown'}" is not allowed.`)
      return
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`File exceeds ${MAX_MB} MB limit.`)
      return
    }
    setError(null)
    uploadMutation.mutate(file)
  }

  return (
    <div style={{ marginTop: 8 }}>
      {/* Attachment list */}
      {attachments.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          {attachments.map((a: Attachment) => (
            <div
              key={a.id}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '4px 6px', marginBottom: 3,
                background: 'var(--surface-2)', border: '1px solid var(--border-subtle)',
                borderRadius: 3,
              }}
            >
              <span style={{ fontSize: 16 }}>{fileIcon(a.content_type)}</span>
              <button
                onClick={() => openAttachment(a)}
                disabled={opening === a.id}
                title={isViewable(a.content_type) ? 'Open' : 'Save'}
                style={{
                  flex: 1, fontSize: 15, color: accent, textAlign: 'left',
                  background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                  textDecoration: 'underline', overflow: 'hidden',
                  textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}
              >
                {opening === a.id ? 'Opening…' : a.filename}
              </button>
              <span style={{ fontSize: 14, color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>
                {formatBytes(a.size_bytes)}
              </span>
              <button
                onClick={() => deleteMutation.mutate(a.id)}
                disabled={deleteMutation.isPending}
                style={{
                  background: 'none', border: 'none', color: '#f43f5e',
                  cursor: 'pointer', fontSize: 15, padding: '0 2px',
                }}
                title="Delete attachment"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }}
        onClick={() => fileInputRef.current?.click()}
        style={{
          border: `1px dashed ${dragOver ? accent : 'var(--border)'}`,
          borderRadius: 4, padding: '8px 10px',
          textAlign: 'center', cursor: 'pointer',
          background: dragOver ? `${accent}08` : 'transparent',
          transition: 'background 0.15s, border-color 0.15s',
        }}
      >
        {uploadMutation.isPending ? (
          <span style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
            Uploading...
          </span>
        ) : (
          <span style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
            ↑ Attach file <span style={{ color: 'var(--text-3)', fontSize: 13 }}>({MAX_MB} MB max)</span>
          </span>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        style={{ display: 'none' }}
        onChange={e => handleFiles(e.target.files)}
      />

      {error && (
        <div style={{ fontSize: 14, color: '#f43f5e', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
          {error}
        </div>
      )}
    </div>
  )
}
