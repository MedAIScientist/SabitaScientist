import { useState, type CSSProperties } from 'react'

/** Local YYYY-MM-DD (toISOString would shift the day in UTC+ time zones). */
export function ymd(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Monday of the week containing d. */
export function mondayOf(d: Date): Date {
  const m = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  m.setDate(m.getDate() - ((m.getDay() + 6) % 7))
  return m
}

function parse(s: string): Date {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

const DAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']

/** Tiny month calendar: click any day to pick its week (Monday-based). */
export function WeekPicker({ value, onChange }: { value: string; onChange: (monday: string) => void }) {
  const [month, setMonth] = useState(() => { const d = parse(value); return new Date(d.getFullYear(), d.getMonth(), 1) })
  const today = ymd(new Date())
  const thisWeek = ymd(mondayOf(new Date()))
  const start = mondayOf(month)
  const weeks = Array.from({ length: 6 }, (_, w) =>
    Array.from({ length: 7 }, (_, i) => { const d = new Date(start); d.setDate(start.getDate() + w * 7 + i); return d }))
    .filter((row, w) => w < 4 || row[0].getMonth() === month.getMonth())
  const shift = (n: number) => setMonth(new Date(month.getFullYear(), month.getMonth() + n, 1))

  return (
    <div className="week-picker" style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 8, fontSize: 12, userSelect: 'none' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <button type="button" aria-label="Previous month" onClick={() => shift(-1)} style={navBtn}>‹</button>
        <strong style={{ color: 'var(--text-heading)' }}>{month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}</strong>
        <button type="button" aria-label="Next month" onClick={() => shift(1)} style={navBtn}>›</button>
      </div>
      <div role="grid" aria-label="Pick a week">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', color: 'var(--text-dim)', textAlign: 'center' }}>
          {DAYS.map(d => <span key={d}>{d}</span>)}
        </div>
        {weeks.map(row => {
          const monday = ymd(row[0])
          const selected = monday === value
          return (
            <button type="button" key={monday} onClick={() => onChange(monday)}
              aria-pressed={selected} aria-label={`Week of ${monday}`}
              style={{
                display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', width: '100%', padding: '2px 0',
                border: monday === thisWeek && !selected ? '1px dashed rgba(var(--accent-rgb),0.5)' : '1px solid transparent',
                borderRadius: 6, cursor: 'pointer', font: 'inherit',
                background: selected ? 'rgba(var(--accent-rgb),0.18)' : 'transparent',
                color: selected ? 'var(--accent)' : 'var(--text)',
              }}>
              {row.map(d => (
                <span key={ymd(d)} style={{
                  textAlign: 'center',
                  opacity: d.getMonth() === month.getMonth() ? 1 : 0.4,
                  fontWeight: ymd(d) === today ? 700 : 400,
                  textDecoration: ymd(d) === today ? 'underline' : 'none',
                }}>{d.getDate()}</span>
              ))}
            </button>
          )
        })}
      </div>
      {value !== thisWeek && (
        <button type="button" onClick={() => { onChange(thisWeek); setMonth(new Date(new Date().getFullYear(), new Date().getMonth(), 1)) }}
          style={{ ...navBtn, width: '100%', marginTop: 4, fontSize: 12 }}>This week</button>
      )}
    </div>
  )
}

const navBtn: CSSProperties = {
  background: 'transparent', border: '1px solid var(--border)', borderRadius: 6,
  color: 'var(--text)', cursor: 'pointer', padding: '1px 8px', font: 'inherit',
}
