interface SectionHeaderProps {
  title: string
  accent?: string
  count?: number
}

export function SectionHeader({ title, accent = '#ff8015', count }: SectionHeaderProps) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      borderLeft: `3px solid ${accent}`,
      paddingLeft: 12,
      marginBottom: 16,
    }}>
      <span style={{
        fontSize: 11,
        fontWeight: 700,
        fontFamily: 'var(--font-mono)',
        letterSpacing: '0.12em',
        textTransform: 'uppercase' as const,
        color: accent,
      }}>
        {title}
      </span>
      {count !== undefined && (
        <span style={{
          fontSize: 10,
          fontFamily: 'var(--font-mono)',
          color: accent,
          background: `${accent}18`,
          border: `1px solid ${accent}33`,
          borderRadius: 9,
          padding: '1px 7px',
        }}>
          {count}
        </span>
      )}
    </div>
  )
}
