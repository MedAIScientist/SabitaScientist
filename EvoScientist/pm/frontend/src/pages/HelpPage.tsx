import { useState, useMemo, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'

const SECTION_STYLES = `
.help-content h1 { font-size: 1.6em; border-bottom: 2px solid #ff8015; padding-bottom: 8px; margin: 0 0 16px; color: var(--text-heading); }
.help-content h2 { font-size: 1.25em; margin: 1.4em 0 0.6em; color: var(--text-heading); }
.help-content h3 { font-size: 1.08em; margin: 1.2em 0 0.4em; }
.help-content p { margin: 0.5em 0; }
.help-content code { background: var(--surface-input); padding: 2px 6px; border-radius: 3px; font-size: 0.9em; font-family: var(--font-mono); }
.help-content pre { background: var(--surface-input); padding: 14px; border-radius: 6px; overflow-x: auto; border: 1px solid var(--border); }
.help-content pre code { background: none; padding: 0; }
.help-content table { border-collapse: collapse; width: 100%; margin: 12px 0; }
.help-content th, .help-content td { border: 1px solid var(--border); padding: 8px 12px; text-align: left; }
.help-content th { background: var(--surface-input); font-weight: 700; }
.help-content blockquote { border-left: 3px solid #ff8015; margin: 12px 0; padding: 8px 16px; background: var(--surface-input); border-radius: 0 4px 4px 0; }
.help-content hr { border: none; border-top: 1px solid var(--border); margin: 24px 0; }
.help-content a { color: #ff8015; }
.help-content img { max-width: 100%; }
.help-content ul, .help-content ol { padding-left: 24px; }
.help-content li { margin: 0.3em 0; }
`

export function HelpPage() {
  const [activeSlug, setActiveSlug] = useState<string | null>(null)
  const tocRef = useRef<HTMLDivElement>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['help'],
    queryFn: () => api.getHelp(),
  })

  const contentSections = useMemo(() => {
    if (!data?.sections) return []
    return data.sections.filter(s => /^\d+-/.test(s.slug))
  }, [data])

  useEffect(() => {
    if (!contentSections.length || activeSlug) return
    setActiveSlug(contentSections[0].slug)
  }, [contentSections, activeSlug])

  useEffect(() => {
    const hash = window.location.hash.slice(1)
    if (hash && contentSections.some(s => s.slug === hash)) {
      setActiveSlug(hash)
    }
  }, [contentSections])

  const activeSection = useMemo(() => {
    if (!contentSections.length || !activeSlug) return null
    return contentSections.find(s => s.slug === activeSlug) ?? contentSections[0]
  }, [contentSections, activeSlug])

  function selectSection(slug: string) {
    setActiveSlug(slug)
    window.location.hash = slug
  }

  if (isLoading) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 19 }}>LOADING…</div>
  }

  if (error || !data) {
    return <div style={{ padding: 40, textAlign: 'center', color: '#f43f5e', fontFamily: 'var(--font-mono)', fontSize: 16 }}>Failed to load help document.</div>
  }

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 48px)', overflow: 'hidden' }}>
      <style>{SECTION_STYLES}</style>

      {/* Sidebar */}
      <div ref={tocRef} style={{
        width: 240, flexShrink: 0, overflowY: 'auto',
        borderRight: '1px solid var(--border)',
        background: 'var(--surface-panel)',
        padding: '16px 0',
      }}>
        <div style={{ padding: '0 16px 12px', fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)', letterSpacing: '0.04em' }}>
          GUIDE
        </div>
        {contentSections.map(s => (
          <button key={s.slug} onClick={() => selectSection(s.slug)} style={{
            display: 'block', width: '100%', textAlign: 'left',
            padding: '7px 16px', cursor: 'pointer', fontSize: 15,
            fontFamily: 'var(--font-mono)',
            background: activeSlug === s.slug ? 'rgba(255,128,21,0.1)' : 'transparent',
            border: 'none', borderLeft: activeSlug === s.slug ? '3px solid #ff8015' : '3px solid transparent',
            color: activeSlug === s.slug ? '#ff8015' : 'var(--text-2)',
            transition: 'background 0.1s',
          }}
            onMouseEnter={e => { if (activeSlug !== s.slug) { e.currentTarget.style.background = 'var(--surface-input)' } }}
            onMouseLeave={e => { if (activeSlug !== s.slug) { e.currentTarget.style.background = 'transparent' } }}
          >{s.title}</button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '28px 32px 60px' }}>
        <div className="help-content" style={{
          maxWidth: 860, margin: '0 auto',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          lineHeight: 1.7, color: 'var(--text)',
        }}>
          {activeSection && (
            <>
              <h2>{activeSection.title}</h2>
              <div dangerouslySetInnerHTML={{ __html: activeSection.html }} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
