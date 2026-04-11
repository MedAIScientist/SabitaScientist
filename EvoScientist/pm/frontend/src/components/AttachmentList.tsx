import { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Attachment } from '../api'

const MAX_MB = 50
const ALLOWED_TYPES = [
  'image/', 'text/', 'application/pdf', 'application/json',
  'application/zip', 'application/gzip', 'application/x-tar', 'application/octet-stream',
]

function isAllowedType(type: string) {
  return ALLOWED_TYPES.some(t => type.startsWith(t))
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function fileIcon(contentType: string): string {
  if (contentType.startsWith('image/')) return '🖼'
  if (contentType === 'application/pdf') return '📄'
  if (contentType.startsWith('text/') || contentType === 'application/json') return '📝'
  if (['application/zip', 'application/gzip', 'application/x-tar'].includes(contentType)) return '📦'
  return '📎'
}

interface Props {
  projectId: string
  expId: string
  entryId: string
  accent: string
}

export function AttachmentList({ projectId, expId, entryId, accent }: Props) {
  const qc = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data: attachments = [] } = useQuery<Attachment[]>({
    queryKey: ['attachments', entryId],
    queryFn: () => api.listAttachments(projectId, expId, entryId),
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadAttachment(projectId, expId, entryId, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['attachments', entryId] })
      setError(null)
    },
    onError: (err: Error) => setError(err.message),
  })

  const deleteMutation = useMutation({
    mutationFn: (attachmentId: string) => api.deleteAttachment(attachmentId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['attachments', entryId] }),
    onError: (err: Error) => setError(err.message),
  })

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
              <a
                href={a.download_url}
                target="_blank"
                rel="noreferrer"
                style={{
                  flex: 1, fontSize: 15, color: accent,
                  textDecoration: 'none', overflow: 'hidden',
                  textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}
              >
                {a.filename}
              </a>
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
            UPLOADING...
          </span>
        ) : (
          <span style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
            ↑ ATTACH FILE <span style={{ color: 'var(--text-3)', fontSize: 13 }}>({MAX_MB} MB max)</span>
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
