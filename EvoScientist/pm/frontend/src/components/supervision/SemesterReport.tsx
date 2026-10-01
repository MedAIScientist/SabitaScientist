import { useState } from 'react'

/** Current and the three previous academic terms ('2026 Fall', '2026 Spring', …). */
function recentTerms(today = new Date()): string[] {
  const y = today.getFullYear(), m = today.getMonth() + 1
  let year = m >= 9 ? y : m === 1 ? y - 1 : y
  let season: 'Fall' | 'Spring' = m >= 9 || m === 1 ? 'Fall' : 'Spring'
  const out: string[] = []
  for (let i = 0; i < 4; i++) {
    out.push(`${year} ${season}`)
    if (season === 'Fall') season = 'Spring'
    else { season = 'Fall'; year -= 1 }
  }
  return out
}

/**
 * Semester progress report: open a print-ready page (Save as PDF from the print dialog)
 * or download it as a Word file. The files need the session token, so they are fetched
 * and handed to the browser rather than linked.
 */
export function SemesterReport({ studentId }: { studentId: string }) {
  const terms = recentTerms()
  const [term, setTerm] = useState(terms[0])
  const [error, setError] = useState<string | null>(null)

  async function fetchBlob(suffix: string): Promise<Blob | null> {
    setError(null)
    const token = sessionStorage.getItem('pm_token')
    const r = await fetch(`/api/v1/supervision/students/${studentId}/semester-report${suffix}?term=${encodeURIComponent(term)}`,
      { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    if (!r.ok) { setError(`Could not prepare the report (HTTP ${r.status}).`); return null }
    return r.blob()
  }

  async function openPrintable() {
    const tab = window.open('', '_blank')  // open first: popup blockers allow it only on the click
    const blob = await fetchBlob('')
    if (!blob) { tab?.close(); return }
    if (tab) tab.location.href = URL.createObjectURL(blob)
  }

  async function downloadWord() {
    const blob = await fetchBlob('.doc')
    if (!blob) return
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `semester-report-${term.replace(' ', '-')}.doc`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <section className="request" aria-label="Semester report">
      <div className="request-head" style={{ marginBottom: 0 }}>
        <div>
          <div className="request-title">Semester progress report</div>
          <div className="request-meta">Weekly updates, feedback, follow-ups, attendance, publications and skills — for TİK and graduate-school forms.</div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <select className="input" style={{ width: 140 }} value={term} onChange={e => setTerm(e.target.value)} aria-label="Term">
            {terms.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <button className="btn" onClick={openPrintable}>Open printable (PDF)</button>
          <button className="btn btn-primary" onClick={downloadWord}>Download Word</button>
        </div>
      </div>
      {error && <div className="msg msg-error" role="alert" style={{ marginTop: 8 }}>{error}</div>}
    </section>
  )
}
