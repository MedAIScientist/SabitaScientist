interface DonutSegment {
  value: number
  color: string
  label: string
}

interface DonutChartProps {
  segments: DonutSegment[]
  size?: number
  strokeWidth?: number
}

export function DonutChart({ segments, size = 120, strokeWidth = 18 }: DonutChartProps) {
  const cx = size / 2
  const cy = size / 2
  const r = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * r
  const total = segments.reduce((sum, s) => sum + s.value, 0)

  if (total === 0) {
    return (
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={cx} cy={cy} r={r}
          fill="none"
          stroke="rgba(100,116,139,0.3)"
          strokeWidth={strokeWidth}
        />
        <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle"
          fontSize={size * 0.12} fill="var(--text-dim)" fontFamily="var(--font-mono)">
          None
        </text>
      </svg>
    )
  }

  let cumulative = 0

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {segments.map((seg, i) => {
        const segLength = (seg.value / total) * circumference
        const dashOffset = circumference - cumulative
        cumulative += segLength
        return (
          <circle
            key={i}
            cx={cx} cy={cy} r={r}
            fill="none"
            stroke={seg.color}
            strokeWidth={strokeWidth}
            strokeDasharray={`${segLength} ${circumference}`}
            strokeDashoffset={dashOffset}
            transform={`rotate(-90 ${cx} ${cy})`}
          />
        )
      })}
      {(() => {
        const largest = segments.reduce(
          (max, s) => s.value > max.value ? s : max,
          segments[0]
        )
        return (
          <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle"
            fontSize={size * 0.12} fill="var(--text-dim)" fontFamily="var(--font-mono)">
            {largest.label}
          </text>
        )
      })()}
    </svg>
  )
}
