import { api } from './api'

/**
 * Opening a stored file is the same problem wherever it is listed.
 *
 * The bytes come from the API rather than a presigned bucket URL, because the
 * object store is only reachable inside the deployment's network. Viewable types
 * are shown in a new tab; everything else is saved, which is what a browser would
 * do with a zip anyway.
 */

/** Types a browser can display in a tab. */
export const VIEWABLE_PREFIXES = [
  'image/',
  'text/',
  'application/pdf',
  'application/json',
]

export function isViewable(contentType: string): boolean {
  return VIEWABLE_PREFIXES.some(prefix => contentType.startsWith(prefix))
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function fileIcon(contentType: string): string {
  if (contentType.startsWith('image/')) return '🖼'
  if (contentType === 'application/pdf') return '📄'
  if (contentType.startsWith('text/') || contentType === 'application/json') return '📝'
  if (['application/zip', 'application/gzip', 'application/x-tar'].includes(contentType)) return '📦'
  return '📎'
}

export async function openAttachmentFile(file: {
  id: string
  filename: string
  content_type: string
}): Promise<void> {
  const blob = await api.fetchAttachmentBlob(file.id)
  const url = URL.createObjectURL(blob)
  if (isViewable(file.content_type)) {
    window.open(url, '_blank', 'noopener')
  } else {
    const link = document.createElement('a')
    link.href = url
    link.download = file.filename
    link.click()
  }
  // Released once the new tab or the download has had time to take the URL.
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}
