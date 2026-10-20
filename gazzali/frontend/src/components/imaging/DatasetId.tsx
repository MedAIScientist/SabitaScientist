import { useState } from 'react'

/**
 * A dataset's id, shown whole and copyable. It is the one key the other systems use: Curator's
 * cohort console lists cohorts by it, an admin links a saved PACS selection to its request with
 * it, and the dataset's bucket is named after it. Without it on screen, matching a request here to
 * a cohort there meant guessing by name.
 */
export function DatasetId({ id }: { id: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    // The clipboard API needs a secure context; without it the id is still selectable by hand.
    navigator.clipboard?.writeText(id).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }, () => undefined)
  }
  return (
    <div className="dataset-id">
      <span>Dataset id</span>
      <code title="Dataset id">{id}</code>
      <button type="button" className="btn" onClick={copy} aria-label="Copy dataset id">{copied ? 'Copied' : 'Copy'}</button>
    </div>
  )
}
