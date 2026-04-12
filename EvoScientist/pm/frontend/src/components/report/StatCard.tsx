interface StatCardProps {
  value: string | number
  label: string
  accent: string
  sublabel?: string
}

export function StatCard({ value, label, accent, sublabel }: StatCardProps) {
  return (
    <div style={{
      background: 'var(--surface-card)',
      border: '1px solid var(--border-subtle)',
      borderLeft: `3px solid ${accent}`,
      borderRadius: '0 8px 8px 0',
      padding: '16px 20px',
      flex: 1,
      minWidth: 0,
    }}>
      <div style={{
        fontSize: 48,
        fontWeight: 700,
        color: 'var(--text-heading)',
        fontFamily: 'var(--font-mono)',
        lineHeight: 1,
        marginBottom: 4,
      }}>
        {value}
      </div>
      {sublabel && (
        <div style={{
          fontSize: 16,
          color: 'var(--text-dim)',
          fontFamily: 'var(--font-mono)',
          marginBottom: 4,
        }}>
          {sublabel}
        </div>
      )}
      <div style={{
        fontSize: 15,
        color: 'var(--text-dim)',
        fontFamily: 'var(--font-mono)',
        letterSpacing: '0.1em',
        textTransform: 'uppercase' as const,
      }}>
        {label}
      </div>
    </div>
  )
}
