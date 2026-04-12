interface BarRow {
  label: string
  value: number
  max: number
  color: string
  sublabel?: string
  segments?: { value: number; color: string }[]
}

interface BarChartProps {
  rows: BarRow[]
  rowHeight?: number
}

export function BarChart({ rows, rowHeight = 28 }: BarChartProps) {
  const gap = 10
  const labelWidth = 150
  const barWidth = 260
  const rightPad = 60
  const totalWidth = labelWidth + barWidth + rightPad
  const totalHeight = rows.length * (rowHeight + gap)

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${totalWidth} ${totalHeight}`}
      style={{ overflow: 'visible', display: 'block' }}
    >
      {rows.map((row, i) => {
        const y = i * (rowHeight + gap)
        const isStacked = Array.isArray(row.segments) && row.segments.length > 0
        const total = isStacked
          ? row.segments!.reduce((s, seg) => s + seg.value, 0)
          : row.max

        return (
          <g key={i}>
            <text
              x={0} y={y + rowHeight / 2}
              dominantBaseline="middle"
              fontSize={11}
              fill="var(--text-dim)"
              fontFamily="var(--font-mono)"
            >
              {row.label.length > 24 ? `${row.label.slice(0, 24)}\u2026` : row.label}
            </text>

            {/* Background track */}
            <rect
              x={labelWidth} y={y + 4}
              width={barWidth} height={rowHeight - 8}
              fill="rgba(100,116,139,0.12)" rx={3}
            />

            {/* Bar(s) */}
            {isStacked ? (
              (() => {
                let xOff = 0
                return row.segments!.map((seg, j) => {
                  const sw = total > 0 ? (seg.value / total) * barWidth : 0
                  const el = (
                    <rect
                      key={j}
                      x={labelWidth + xOff} y={y + 4}
                      width={sw} height={rowHeight - 8}
                      fill={seg.color}
                      rx={j === 0 ? 3 : 0}
                    />
                  )
                  xOff += sw
                  return el
                })
              })()
            ) : (
              <rect
                x={labelWidth} y={y + 4}
                width={total > 0 ? (row.value / total) * barWidth : 0}
                height={rowHeight - 8}
                fill={row.color} rx={3}
              />
            )}

            {/* Value / sublabel */}
            <text
              x={labelWidth + barWidth + 8}
              y={y + rowHeight / 2}
              dominantBaseline="middle"
              fontSize={10}
              fill="var(--text-dim)"
              fontFamily="var(--font-mono)"
            >
              {row.sublabel !== undefined ? row.sublabel : String(row.value)}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
