# Report Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Reports module with per-project detailed reports and a global cross-project analytics view, using hand-rolled SVG charts and browser PDF export.

**Architecture:** Two new route-level pages (`ProjectReportPage`, `GlobalReportPage`) share four small presentational components in `src/components/report/`. All data comes from existing API endpoints via TanStack Query — no new backend routes needed. Charts are pure SVG using `stroke-dasharray` for donuts and `<rect>` elements for bars.

**Tech Stack:** React 18, TypeScript, TanStack Query v5, React Router v6, Vitest + Testing Library, browser `window.print()` API.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/components/report/SectionHeader.tsx` | Create | Mono uppercase heading with accent left border |
| `src/components/report/StatCard.tsx` | Create | Large value + label card with accent left border |
| `src/components/report/DonutChart.tsx` | Create | SVG multi-segment donut chart |
| `src/components/report/BarChart.tsx` | Create | SVG horizontal bar chart (simple + stacked) |
| `src/components/report/__tests__/report-components.test.tsx` | Create | Unit tests for all four shared components |
| `src/pages/ProjectReportPage.tsx` | Create | `/projects/:id/report` — full per-project report |
| `src/pages/GlobalReportPage.tsx` | Create | `/reports` — cross-project analytics |
| `src/pages/__tests__/ProjectReportPage.test.tsx` | Create | Integration tests for ProjectReportPage |
| `src/pages/__tests__/GlobalReportPage.test.tsx` | Create | Integration tests for GlobalReportPage |
| `src/main.tsx` | Modify | Add two new private routes |
| `src/pages/Board.tsx` | Modify | Add 📊 REPORT button in header |
| `src/pages/Projects.tsx` | Modify | Add 📊 REPORTS button in header |

---

## Context for implementers

**Project root:** `EvoScientist/pm/frontend/`

**Run tests:** `npm run test` (Vitest watch) or `npm run test -- --run` (single pass)

**Run build:** `npm run build` (must pass TypeScript before deploy)

**Key existing patterns to follow:**
- Inline styles using CSS variables (`var(--bg)`, `var(--surface-card)`, `var(--text-heading)`, `var(--font-mono)`, `var(--border-subtle)`)
- Brand colors: orange `#ff8015`, amber `#f59e0b`, green `#10b981`, rose `#f43f5e`, purple `#8b5cf6`
- `useQuery` from `@tanstack/react-query` for data fetching; query keys are `['project', id]`, `['tasks', id]`, `['experiments', id]`
- `useParams<{ id: string }>()` and `useNavigate()` from `react-router-dom`
- Auth via `useAuth()` from `../auth`
- Test wrapper pattern (see `src/pages/__tests__/ExperimentsPage.test.tsx`):
  ```tsx
  function wrap(ui) {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    return (
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/projects/p1/report']}>
          <Routes><Route path="/projects/:id/report" element={ui} /></Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )
  }
  ```

---

## Task 1: Shared UI components — SectionHeader + StatCard

**Files:**
- Create: `EvoScientist/pm/frontend/src/components/report/SectionHeader.tsx`
- Create: `EvoScientist/pm/frontend/src/components/report/StatCard.tsx`
- Create: `EvoScientist/pm/frontend/src/components/report/__tests__/report-components.test.tsx`

- [ ] **Step 1: Write failing tests**

```tsx
// src/components/report/__tests__/report-components.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { SectionHeader } from '../SectionHeader'
import { StatCard } from '../StatCard'

describe('SectionHeader', () => {
  it('renders title text', () => {
    render(<SectionHeader title="Task Breakdown" />)
    expect(screen.getByText('Task Breakdown')).toBeInTheDocument()
  })

  it('renders count badge when provided', () => {
    render(<SectionHeader title="Tasks" count={12} />)
    expect(screen.getByText('12')).toBeInTheDocument()
  })

  it('does not render badge when count is undefined', () => {
    const { container } = render(<SectionHeader title="Tasks" />)
    expect(container.querySelectorAll('span').length).toBe(1)
  })
})

describe('StatCard', () => {
  it('renders value and label', () => {
    render(<StatCard value={42} label="Total Tasks" accent="#ff8015" />)
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText('Total Tasks')).toBeInTheDocument()
  })

  it('renders sublabel when provided', () => {
    render(<StatCard value="75%" label="Done" accent="#10b981" sublabel="of 8 total" />)
    expect(screen.getByText('of 8 total')).toBeInTheDocument()
  })

  it('renders string value', () => {
    render(<StatCard value="75%" label="Done" accent="#10b981" />)
    expect(screen.getByText('75%')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd EvoScientist/pm/frontend
npm run test -- --run src/components/report/__tests__/report-components.test.tsx
```

Expected: FAIL — `Cannot find module '../SectionHeader'`

- [ ] **Step 3: Create SectionHeader**

```tsx
// src/components/report/SectionHeader.tsx
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
```

- [ ] **Step 4: Create StatCard**

```tsx
// src/components/report/StatCard.tsx
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
        fontSize: 32,
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
          fontSize: 11,
          color: 'var(--text-dim)',
          fontFamily: 'var(--font-mono)',
          marginBottom: 4,
        }}>
          {sublabel}
        </div>
      )}
      <div style={{
        fontSize: 10,
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
npm run test -- --run src/components/report/__tests__/report-components.test.tsx
```

Expected: all 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add EvoScientist/pm/frontend/src/components/report/
git commit -m "feat(report): add SectionHeader and StatCard components"
```

---

## Task 2: DonutChart component

**Files:**
- Create: `EvoScientist/pm/frontend/src/components/report/DonutChart.tsx`
- Modify: `EvoScientist/pm/frontend/src/components/report/__tests__/report-components.test.tsx`

- [ ] **Step 1: Add failing DonutChart tests** (append to existing test file)

```tsx
// Add to src/components/report/__tests__/report-components.test.tsx
import { DonutChart } from '../DonutChart'

describe('DonutChart', () => {
  it('renders an SVG element', () => {
    const { container } = render(
      <DonutChart segments={[
        { value: 3, color: '#ff8015', label: 'PLANNED' },
        { value: 5, color: '#10b981', label: 'DONE' },
      ]} />
    )
    expect(container.querySelector('svg')).toBeInTheDocument()
  })

  it('renders one circle per segment', () => {
    const { container } = render(
      <DonutChart segments={[
        { value: 3, color: '#ff8015', label: 'A' },
        { value: 5, color: '#10b981', label: 'B' },
      ]} />
    )
    expect(container.querySelectorAll('circle').length).toBe(2)
  })

  it('renders empty state circle when total is 0', () => {
    const { container } = render(
      <DonutChart segments={[{ value: 0, color: '#ff8015', label: 'NONE' }]} />
    )
    expect(container.querySelectorAll('circle').length).toBe(1)
  })

  it('shows label of largest segment in center', () => {
    render(
      <DonutChart segments={[
        { value: 2, color: '#ff8015', label: 'SMALL' },
        { value: 8, color: '#10b981', label: 'BIG' },
      ]} />
    )
    expect(screen.getByText('BIG')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
npm run test -- --run src/components/report/__tests__/report-components.test.tsx
```

Expected: FAIL — `Cannot find module '../DonutChart'`

- [ ] **Step 3: Create DonutChart**

```tsx
// src/components/report/DonutChart.tsx
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npm run test -- --run src/components/report/__tests__/report-components.test.tsx
```

Expected: all 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/frontend/src/components/report/DonutChart.tsx \
        EvoScientist/pm/frontend/src/components/report/__tests__/report-components.test.tsx
git commit -m "feat(report): add DonutChart SVG component"
```

---

## Task 3: BarChart component

**Files:**
- Create: `EvoScientist/pm/frontend/src/components/report/BarChart.tsx`
- Modify: `EvoScientist/pm/frontend/src/components/report/__tests__/report-components.test.tsx`

- [ ] **Step 1: Add failing BarChart tests** (append to existing test file)

```tsx
// Add to src/components/report/__tests__/report-components.test.tsx
import { BarChart } from '../BarChart'

describe('BarChart', () => {
  const simpleRows = [
    { label: 'Project Alpha', value: 3, max: 10, color: '#10b981' },
    { label: 'Project Beta',  value: 7, max: 10, color: '#f59e0b' },
  ]

  it('renders an SVG element', () => {
    const { container } = render(<BarChart rows={simpleRows} />)
    expect(container.querySelector('svg')).toBeInTheDocument()
  })

  it('renders a label for each row', () => {
    render(<BarChart rows={simpleRows} />)
    expect(screen.getByText('Project Alpha')).toBeInTheDocument()
    expect(screen.getByText('Project Beta')).toBeInTheDocument()
  })

  it('truncates long labels', () => {
    render(<BarChart rows={[{ label: 'A Very Long Project Name Indeed Here', value: 1, max: 10, color: '#ff8015' }]} />)
    expect(screen.getByText(/A Very Long Project Name/)).toBeInTheDocument()
  })

  it('renders sublabel when provided', () => {
    render(<BarChart rows={[{ label: 'X', value: 5, max: 10, color: '#ff8015', sublabel: '50%' }]} />)
    expect(screen.getByText('50%')).toBeInTheDocument()
  })

  it('renders stacked bars when segments provided', () => {
    const stackedRows = [{
      label: 'Project X', value: 6, max: 6, color: '#ff8015',
      segments: [
        { value: 2, color: '#f59e0b' },
        { value: 3, color: '#ff8015' },
        { value: 1, color: '#10b981' },
      ],
    }]
    const { container } = render(<BarChart rows={stackedRows} />)
    // 1 background rect + 3 segment rects
    expect(container.querySelectorAll('rect').length).toBeGreaterThanOrEqual(4)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
npm run test -- --run src/components/report/__tests__/report-components.test.tsx
```

Expected: FAIL — `Cannot find module '../BarChart'`

- [ ] **Step 3: Create BarChart**

```tsx
// src/components/report/BarChart.tsx
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
              {row.label.length > 20 ? `${row.label.slice(0, 20)}…` : row.label}
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npm run test -- --run src/components/report/__tests__/report-components.test.tsx
```

Expected: all 15 tests PASS

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/frontend/src/components/report/BarChart.tsx \
        EvoScientist/pm/frontend/src/components/report/__tests__/report-components.test.tsx
git commit -m "feat(report): add BarChart SVG component with stacked support"
```

---

## Task 4: ProjectReportPage

**Files:**
- Create: `EvoScientist/pm/frontend/src/pages/ProjectReportPage.tsx`
- Create: `EvoScientist/pm/frontend/src/pages/__tests__/ProjectReportPage.test.tsx`

- [ ] **Step 1: Write failing tests**

```tsx
// src/pages/__tests__/ProjectReportPage.test.tsx
import React from 'react'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ProjectReportPage } from '../ProjectReportPage'
import type { Task, Experiment, ExperimentEntry } from '../../api'

vi.mock('../../api', () => ({
  api: {
    getProject: vi.fn().mockResolvedValue({
      id: 'p1', name: 'CRISPR Study',
      members: [
        { user_id: 'u1', username: 'alice', role: 'owner', added_at: '' },
        { user_id: 'u2', username: 'bob',   role: 'editor', added_at: '' },
      ],
      description: null, created_by: 'u1',
      created_at: '2026-01-01', archived_at: null,
    }),
    listTasks: vi.fn().mockResolvedValue([]),
    listExperiments: vi.fn().mockResolvedValue([]),
    listEntries: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('../../auth', () => ({
  useAuth: vi.fn(() => ({ username: 'alice', token: 'tok' })),
}))

vi.mock('../../theme', () => ({
  useTheme: vi.fn(() => ({ theme: 'dark' })),
}))

const MOCK_TASKS: Task[] = [
  { id: 't1', project_id: 'p1', title: 'Task A', description: null,
    assignee_id: 'u1', status: 'done', priority: 'high', deadline: null,
    session_id: null, created_by: 'u1', created_at: '', updated_at: '' },
  { id: 't2', project_id: 'p1', title: 'Task B', description: null,
    assignee_id: null, status: 'todo', priority: 'medium', deadline: null,
    session_id: null, created_by: 'u1', created_at: '', updated_at: '' },
]

const MOCK_EXP: Experiment = {
  id: 'e1', project_id: 'p1', name: 'Western Blot',
  hypothesis: 'Protein is expressed', protocol: 'Run gel', status: 'running',
  tags: ['blot'], deadline: null, created_by: 'u1',
  created_at: '2026-01-01', updated_at: '2026-01-01',
}

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/projects/p1/report']}>
        <Routes>
          <Route path="/projects/:id/report" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ProjectReportPage', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('renders project name in header', async () => {
    render(wrap(<ProjectReportPage />))
    await waitFor(() => expect(screen.getByText('CRISPR Study')).toBeInTheDocument())
  })

  it('shows 0 tasks when no tasks', async () => {
    render(wrap(<ProjectReportPage />))
    await waitFor(() => expect(screen.getByText('0')).toBeInTheDocument())
  })

  it('shows correct done percentage', async () => {
    const { api } = await import('../../api')
    vi.mocked(api.listTasks).mockResolvedValue(MOCK_TASKS)
    render(wrap(<ProjectReportPage />))
    await waitFor(() => expect(screen.getByText('50%')).toBeInTheDocument())
  })

  it('shows experiment name in table', async () => {
    const { api } = await import('../../api')
    vi.mocked(api.listExperiments).mockResolvedValue([MOCK_EXP])
    render(wrap(<ProjectReportPage />))
    await waitFor(() => expect(screen.getAllByText('Western Blot').length).toBeGreaterThanOrEqual(1))
  })

  it('shows team members', async () => {
    render(wrap(<ProjectReportPage />))
    await waitFor(() => {
      expect(screen.getByText('alice')).toBeInTheDocument()
      expect(screen.getByText('bob')).toBeInTheDocument()
    })
  })

  it('expands experiment accordion on click', async () => {
    const { api } = await import('../../api')
    vi.mocked(api.listExperiments).mockResolvedValue([MOCK_EXP])
    render(wrap(<ProjectReportPage />))
    await waitFor(() => screen.getAllByText('Western Blot'))
    const buttons = screen.getAllByRole('button')
    const accordionBtn = buttons.find(b => b.textContent?.includes('Western Blot'))
    expect(accordionBtn).toBeTruthy()
    fireEvent.click(accordionBtn!)
    await waitFor(() => expect(screen.getByText('Protein is expressed')).toBeInTheDocument())
  })

  it('renders PDF button', async () => {
    render(wrap(<ProjectReportPage />))
    await waitFor(() => expect(screen.getByText(/PDF/i)).toBeInTheDocument())
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
npm run test -- --run src/pages/__tests__/ProjectReportPage.test.tsx
```

Expected: FAIL — `Cannot find module '../ProjectReportPage'`

- [ ] **Step 3: Create ProjectReportPage**

```tsx
// src/pages/ProjectReportPage.tsx
import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { StatCard } from '../components/report/StatCard'
import { DonutChart } from '../components/report/DonutChart'
import { BarChart } from '../components/report/BarChart'
import { SectionHeader } from '../components/report/SectionHeader'

const PRINT_CSS = `
@media print {
  .no-print { display: none !important; }
  body { background: white !important; color: black !important; }
  .report-section { break-inside: avoid; }
  .report-section--experiments { break-before: page; }
  .report-section--team { break-before: page; }
  .accordion-body { display: block !important; }
  @page { size: A4; margin: 20mm; }
}
`

const EXP_STATUS_COLORS: Record<string, string> = {
  planned: '#f59e0b',
  running: '#ff8015',
  completed: '#10b981',
}

const PRIORITY_COLORS: Record<string, string> = {
  high: '#f43f5e',
  medium: '#f59e0b',
  low: '#10b981',
}

const AVATAR_COLORS = ['#6366f1', '#ec4899', '#f59e0b', '#ff8015', '#10b981', '#8b5cf6']

const ROLE_COLORS: Record<string, string> = {
  owner: '#ff8015',
  editor: '#f59e0b',
  viewer: '#64748b',
}

function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '8px 12px',
      background: 'rgba(244,63,94,0.08)',
      border: '1px solid rgba(244,63,94,0.2)',
      borderRadius: 6, marginBottom: 12,
    }}>
      <span style={{ fontSize: 11, color: '#f43f5e', fontFamily: 'var(--font-mono)', flex: 1 }}>
        {message}
      </span>
      <button
        onClick={onRetry}
        style={{
          background: 'none',
          border: '1px solid rgba(244,63,94,0.3)',
          borderRadius: 4, color: '#f43f5e',
          fontSize: 10, cursor: 'pointer',
          padding: '3px 8px', fontFamily: 'var(--font-mono)',
        }}
      >
        RETRY
      </button>
    </div>
  )
}

export function ProjectReportPage() {
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [expandedExp, setExpandedExp] = useState<string | null>(null)

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.getProject(projectId!),
    enabled: Boolean(projectId),
  })

  const {
    data: tasks = [],
    isError: tasksError,
    refetch: refetchTasks,
  } = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => api.listTasks(projectId!),
    enabled: Boolean(projectId),
  })

  const { data: experiments = [] } = useQuery({
    queryKey: ['experiments', projectId],
    queryFn: () => api.listExperiments(projectId!),
    enabled: Boolean(projectId),
  })

  const { data: entryCounts = new Map<string, { notes: number; results: number }>() } = useQuery({
    queryKey: ['entryCounts', projectId, experiments.map(e => e.id).join(',')],
    queryFn: async () => {
      const results = await Promise.all(
        experiments.map(async (exp) => {
          const entries = await api.listEntries(projectId!, exp.id)
          return [exp.id, {
            notes: entries.filter(e => e.type === 'note').length,
            results: entries.filter(e => e.type === 'result').length,
          }] as const
        })
      )
      return new Map(results)
    },
    enabled: experiments.length > 0,
  })

  const todoCount       = tasks.filter(t => t.status === 'todo').length
  const inProgressCount = tasks.filter(t => t.status === 'in_progress').length
  const doneCount       = tasks.filter(t => t.status === 'done').length
  const donePercent     = tasks.length > 0 ? Math.round((doneCount / tasks.length) * 100) : 0

  const plannedCount   = experiments.filter(e => e.status === 'planned').length
  const runningCount   = experiments.filter(e => e.status === 'running').length
  const completedCount = experiments.filter(e => e.status === 'completed').length

  const sortedExps = [...experiments].sort((a, b) => {
    const order = { completed: 0, running: 1, planned: 2 }
    return order[a.status] - order[b.status]
  })

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <style>{PRINT_CSS}</style>

      {/* ── Header ── */}
      <div className="no-print" style={{
        padding: '0 28px', height: 54,
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'var(--surface-header)', backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            onClick={() => navigate(`/projects/${projectId}`)}
            style={{
              cursor: 'pointer', background: 'var(--surface-input)',
              border: '1px solid var(--border)', borderRadius: 6,
              color: 'var(--text-muted)', padding: '3px 9px', fontSize: 15, lineHeight: 1,
            }}
          >←</button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <img src="/sabita.jpg" alt="SABITA" style={{ height: 26, borderRadius: 4, display: 'block' }} />
            <span style={{ color: 'var(--text-dim)', fontSize: 13, fontFamily: 'var(--font-mono)' }}>/</span>
            <span style={{ color: '#ff8015', fontSize: 14, fontFamily: 'var(--font-mono)' }}>
              {project?.name ?? '…'}
            </span>
            <span style={{ color: 'var(--text-dim)', fontSize: 13, fontFamily: 'var(--font-mono)' }}>/</span>
            <span style={{ color: 'var(--text-muted)', fontSize: 13, fontFamily: 'var(--font-mono)' }}>report</span>
          </div>
        </div>
        <button
          onClick={() => window.print()}
          style={{
            background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.18)',
            color: '#10b981', fontFamily: 'var(--font-mono)', fontSize: 11,
            padding: '5px 14px', borderRadius: 4, cursor: 'pointer', letterSpacing: '0.08em',
          }}
        >
          ⬇ PDF
        </button>
      </div>

      {/* ── Content ── */}
      <div style={{ maxWidth: 900, margin: '0 auto', padding: '32px 28px 64px' }}>

        {/* Section 1 — Summary */}
        <div className="report-section" style={{ marginBottom: 40 }}>
          <SectionHeader title="Summary" accent="#ff8015" />
          {tasksError && (
            <ErrorBanner
              message="Could not load task data — please retry."
              onRetry={() => refetchTasks()}
            />
          )}
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <StatCard value={tasks.length}           label="Total Tasks"   accent="#ff8015" />
            <StatCard value={`${donePercent}%`}      label="Done"          accent="#10b981" sublabel={`${doneCount} of ${tasks.length}`} />
            <StatCard value={experiments.length}     label="Experiments"   accent="#f59e0b" />
            <StatCard value={project?.members.length ?? 0} label="Team Members" accent="#8b5cf6" />
          </div>
        </div>

        {/* Section 2 — Task Breakdown */}
        <div className="report-section" style={{ marginBottom: 40 }}>
          <SectionHeader title="Task Breakdown" accent="#ff8015" count={tasks.length} />
          <div style={{ display: 'flex', gap: 32, alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <DonutChart
              segments={[
                { value: todoCount,       color: '#ff8015', label: 'PLANNED' },
                { value: inProgressCount, color: '#f59e0b', label: 'IN PROG' },
                { value: doneCount,       color: '#10b981', label: 'DONE' },
              ]}
              size={140}
              strokeWidth={22}
            />
            <div style={{ flex: 1, minWidth: 200 }}>
              {[
                { label: 'PLANNED',     count: todoCount,       color: '#ff8015' },
                { label: 'IN PROGRESS', count: inProgressCount, color: '#f59e0b' },
                { label: 'DONE',        count: doneCount,       color: '#10b981' },
              ].map(({ label, count, color }) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: color, flexShrink: 0 }} />
                  <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', flex: 1 }}>{label}</span>
                  <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-heading)' }}>{count}</span>
                  <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', width: 36, textAlign: 'right' }}>
                    {tasks.length > 0 ? Math.round((count / tasks.length) * 100) : 0}%
                  </span>
                </div>
              ))}
              <div style={{ marginTop: 16, borderTop: '1px solid var(--border-subtle)', paddingTop: 12 }}>
                <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.1em', marginBottom: 8 }}>
                  PRIORITY BREAKDOWN
                </div>
                {(['high', 'medium', 'low'] as const).map(pri => {
                  const count = tasks.filter(t => t.priority === pri).length
                  return (
                    <div key={pri} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: PRIORITY_COLORS[pri], flexShrink: 0 }} />
                      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', flex: 1, textTransform: 'capitalize' }}>{pri}</span>
                      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)', fontWeight: 700 }}>{count}</span>
                      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', width: 36, textAlign: 'right' }}>
                        {tasks.length > 0 ? Math.round((count / tasks.length) * 100) : 0}%
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Section 3 — Experiment Overview */}
        <div className="report-section report-section--experiments" style={{ marginBottom: 40 }}>
          <SectionHeader title="Experiment Overview" accent="#10b981" count={experiments.length} />
          <div style={{ display: 'flex', gap: 32, alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: 20 }}>
            <DonutChart
              segments={[
                { value: plannedCount,   color: '#f59e0b', label: 'PLANNED' },
                { value: runningCount,   color: '#ff8015', label: 'RUNNING' },
                { value: completedCount, color: '#10b981', label: 'DONE' },
              ]}
              size={140}
              strokeWidth={22}
            />
            <div style={{ flex: 1, minWidth: 200 }}>
              {[
                { label: 'PLANNED',   count: plannedCount,   color: '#f59e0b' },
                { label: 'RUNNING',   count: runningCount,   color: '#ff8015' },
                { label: 'COMPLETED', count: completedCount, color: '#10b981' },
              ].map(({ label, count, color }) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: color, flexShrink: 0 }} />
                  <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', flex: 1 }}>{label}</span>
                  <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-heading)' }}>{count}</span>
                </div>
              ))}
            </div>
          </div>
          {/* Experiment table */}
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['NAME', 'STATUS', 'TAGS', 'DEADLINE', 'NOTES', 'RESULTS'].map(h => (
                  <th key={h} style={{ padding: '6px 8px', textAlign: 'left', fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.1em' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedExps.map(exp => {
                const counts = entryCounts.get(exp.id) ?? { notes: 0, results: 0 }
                const statusColor = EXP_STATUS_COLORS[exp.status] ?? '#64748b'
                return (
                  <tr key={exp.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '8px', color: 'var(--text-heading)', fontWeight: 500 }}>{exp.name}</td>
                    <td style={{ padding: '8px' }}>
                      <span style={{
                        fontSize: 9, fontWeight: 700, fontFamily: 'var(--font-mono)',
                        color: statusColor, background: `${statusColor}18`,
                        border: `1px solid ${statusColor}33`,
                        borderRadius: 3, padding: '2px 6px',
                      }}>
                        {exp.status.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: '8px', fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                      {exp.tags.join(', ') || '—'}
                    </td>
                    <td style={{ padding: '8px', fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                      {exp.deadline ?? '—'}
                    </td>
                    <td style={{ padding: '8px', fontSize: 11, textAlign: 'center' }}>{counts.notes}</td>
                    <td style={{ padding: '8px', fontSize: 11, textAlign: 'center' }}>{counts.results}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Section 4 — Experiment Details */}
        <div className="report-section" style={{ marginBottom: 40 }}>
          <SectionHeader title="Experiment Details" accent="#10b981" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {sortedExps.map(exp => {
              const isOpen = expandedExp === exp.id
              const counts = entryCounts.get(exp.id) ?? { notes: 0, results: 0 }
              const statusColor = EXP_STATUS_COLORS[exp.status] ?? '#64748b'
              return (
                <div key={exp.id} style={{ border: '1px solid var(--border-subtle)', borderRadius: 6, overflow: 'hidden' }}>
                  <button
                    onClick={() => setExpandedExp(isOpen ? null : exp.id)}
                    style={{
                      width: '100%', background: 'var(--surface-2)', border: 'none',
                      padding: '10px 14px', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: 10,
                      textAlign: 'left',
                    }}
                  >
                    <span style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                      {isOpen ? '▾' : '▸'}
                    </span>
                    <span style={{ flex: 1, fontSize: 13, fontWeight: 500, color: 'var(--text-heading)' }}>
                      {exp.name}
                    </span>
                    <span style={{
                      fontSize: 9, fontWeight: 700, fontFamily: 'var(--font-mono)',
                      color: statusColor, background: `${statusColor}18`,
                      border: `1px solid ${statusColor}33`,
                      borderRadius: 3, padding: '2px 6px',
                    }}>
                      {exp.status.toUpperCase()}
                    </span>
                  </button>
                  {isOpen && (
                    <div className="accordion-body" style={{
                      padding: '14px 16px',
                      borderTop: '1px solid var(--border-subtle)',
                      background: 'var(--surface-card)',
                    }}>
                      {exp.hypothesis && (
                        <div style={{ marginBottom: 10 }}>
                          <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.1em', marginBottom: 4 }}>
                            HYPOTHESIS
                          </div>
                          <p style={{ fontSize: 12, color: 'var(--text)', lineHeight: 1.5, margin: 0 }}>
                            {exp.hypothesis.slice(0, 200)}{exp.hypothesis.length > 200 ? '…' : ''}
                          </p>
                        </div>
                      )}
                      {exp.protocol && (
                        <div style={{ marginBottom: 10 }}>
                          <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.1em', marginBottom: 4 }}>
                            PROTOCOL
                          </div>
                          <p style={{ fontSize: 12, color: 'var(--text)', lineHeight: 1.5, margin: 0 }}>
                            {exp.protocol.slice(0, 200)}{exp.protocol.length > 200 ? '…' : ''}
                          </p>
                        </div>
                      )}
                      <div style={{ display: 'flex', gap: 16, marginTop: 10 }}>
                        <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
                          <span style={{ color: '#f59e0b', fontWeight: 700 }}>{counts.notes}</span> notes
                        </span>
                        <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
                          <span style={{ color: '#10b981', fontWeight: 700 }}>{counts.results}</span> results
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Section 5 — Team Activity */}
        <div className="report-section report-section--team" style={{ marginBottom: 40 }}>
          <SectionHeader title="Team Activity" accent="#8b5cf6" count={project?.members.length} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {(project?.members ?? []).map((member, i) => {
              const assigned  = tasks.filter(t => t.assignee_id === member.user_id).length
              const completed = tasks.filter(t => t.assignee_id === member.user_id && t.status === 'done').length
              const roleColor = ROLE_COLORS[member.role] ?? '#64748b'
              return (
                <div key={member.user_id} style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  background: 'var(--surface-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 7, padding: '10px 14px',
                }}>
                  <span style={{
                    width: 34, height: 34, borderRadius: '50%',
                    background: AVATAR_COLORS[i % AVATAR_COLORS.length],
                    color: '#fff',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)', flexShrink: 0,
                  }}>
                    {member.username[0].toUpperCase()}
                  </span>
                  <span style={{ flex: 1, fontSize: 13, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)' }}>
                    {member.username}
                  </span>
                  <span style={{
                    fontSize: 9, fontWeight: 700, fontFamily: 'var(--font-mono)',
                    color: roleColor, background: `${roleColor}18`,
                    border: `1px solid ${roleColor}33`,
                    borderRadius: 3, padding: '2px 6px',
                  }}>
                    {member.role.toUpperCase()}
                  </span>
                  <div style={{ display: 'flex', gap: 16, fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                    <span style={{ color: 'var(--text-dim)' }}>
                      Assigned: <strong style={{ color: 'var(--text-heading)' }}>{assigned}</strong>
                    </span>
                    <span style={{ color: 'var(--text-dim)' }}>
                      Done: <strong style={{ color: '#10b981' }}>{completed}</strong>
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npm run test -- --run src/pages/__tests__/ProjectReportPage.test.tsx
```

Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/frontend/src/pages/ProjectReportPage.tsx \
        EvoScientist/pm/frontend/src/pages/__tests__/ProjectReportPage.test.tsx
git commit -m "feat(report): add ProjectReportPage with all 5 sections"
```

---

## Task 5: GlobalReportPage

**Files:**
- Create: `EvoScientist/pm/frontend/src/pages/GlobalReportPage.tsx`
- Create: `EvoScientist/pm/frontend/src/pages/__tests__/GlobalReportPage.test.tsx`

- [ ] **Step 1: Write failing tests**

```tsx
// src/pages/__tests__/GlobalReportPage.test.tsx
import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { GlobalReportPage } from '../GlobalReportPage'
import type { Project, Task, Experiment } from '../../api'

const MOCK_PROJECTS: Project[] = [
  {
    id: 'p1', name: 'CRISPR Study', description: null,
    created_by: 'u1', created_at: '2026-01-01', archived_at: null,
    members: [{ user_id: 'u1', username: 'alice', role: 'owner', added_at: '' }],
  },
  {
    id: 'p2', name: 'Proteomics', description: null,
    created_by: 'u1', created_at: '2026-01-02', archived_at: null,
    members: [{ user_id: 'u1', username: 'alice', role: 'owner', added_at: '' }],
  },
]

const MOCK_TASKS_P1: Task[] = [
  { id: 't1', project_id: 'p1', title: 'Task A', description: null,
    assignee_id: null, status: 'done', priority: 'high', deadline: null,
    session_id: null, created_by: 'u1', created_at: '', updated_at: '' },
]

const MOCK_EXP: Experiment = {
  id: 'e1', project_id: 'p1', name: 'Western Blot', hypothesis: null,
  protocol: null, status: 'running', tags: [], deadline: null,
  created_by: 'u1', created_at: '2026-01-01', updated_at: '2026-01-01',
}

vi.mock('../../api', () => ({
  api: {
    listProjects: vi.fn().mockResolvedValue([]),
    listTasks: vi.fn().mockResolvedValue([]),
    listExperiments: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('../../theme', () => ({
  useTheme: vi.fn(() => ({ theme: 'dark' })),
}))

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/reports']}>
        <Routes>
          <Route path="/reports" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('GlobalReportPage', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('renders reports heading', async () => {
    render(wrap(<GlobalReportPage />))
    await waitFor(() => expect(screen.getByText('reports')).toBeInTheDocument())
  })

  it('shows 0 total projects with empty list', async () => {
    render(wrap(<GlobalReportPage />))
    await waitFor(() => expect(screen.getByText('0')).toBeInTheDocument())
  })

  it('shows project names when projects exist', async () => {
    const { api } = await import('../../api')
    vi.mocked(api.listProjects).mockResolvedValue(MOCK_PROJECTS)
    vi.mocked(api.listTasks).mockImplementation((id) =>
      Promise.resolve(id === 'p1' ? MOCK_TASKS_P1 : [])
    )
    vi.mocked(api.listExperiments).mockImplementation((id) =>
      Promise.resolve(id === 'p1' ? [MOCK_EXP] : [])
    )
    render(wrap(<GlobalReportPage />))
    await waitFor(() => {
      expect(screen.getByText('CRISPR Study')).toBeInTheDocument()
      expect(screen.getByText('Proteomics')).toBeInTheDocument()
    })
  })

  it('shows VIEW REPORT links for each project', async () => {
    const { api } = await import('../../api')
    vi.mocked(api.listProjects).mockResolvedValue(MOCK_PROJECTS)
    vi.mocked(api.listTasks).mockResolvedValue([])
    vi.mocked(api.listExperiments).mockResolvedValue([])
    render(wrap(<GlobalReportPage />))
    await waitFor(() => {
      const links = screen.getAllByText(/VIEW REPORT/)
      expect(links.length).toBe(2)
    })
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
npm run test -- --run src/pages/__tests__/GlobalReportPage.test.tsx
```

Expected: FAIL — `Cannot find module '../GlobalReportPage'`

- [ ] **Step 3: Create GlobalReportPage**

```tsx
// src/pages/GlobalReportPage.tsx
import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, Project, Task, Experiment } from '../api'
import { StatCard } from '../components/report/StatCard'
import { BarChart } from '../components/report/BarChart'
import { SectionHeader } from '../components/report/SectionHeader'

function completionColor(pct: number): string {
  if (pct >= 70) return '#10b981'
  if (pct >= 30) return '#f59e0b'
  return '#f43f5e'
}

export function GlobalReportPage() {
  const navigate = useNavigate()

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: api.listProjects,
  })

  const { data: allProjectData = [] } = useQuery({
    queryKey: ['globalReport', projects.map(p => p.id).join(',')],
    queryFn: async () => {
      const results = await Promise.all(
        projects.map(async (project) => {
          const [tasks, experiments] = await Promise.all([
            api.listTasks(project.id),
            api.listExperiments(project.id),
          ])
          return { project, tasks, experiments }
        })
      )
      return results as { project: Project; tasks: Task[]; experiments: Experiment[] }[]
    },
    enabled: projects.length > 0,
  })

  const totalTasks   = allProjectData.reduce((sum, { tasks }) => sum + tasks.length, 0)
  const totalDone    = allProjectData.reduce((sum, { tasks }) => sum + tasks.filter(t => t.status === 'done').length, 0)
  const totalExps    = allProjectData.reduce((sum, { experiments }) => sum + experiments.length, 0)
  const runningExps  = allProjectData.reduce((sum, { experiments }) => sum + experiments.filter(e => e.status === 'running').length, 0)

  const taskCompletionRows = allProjectData.map(({ project, tasks }) => {
    const done  = tasks.filter(t => t.status === 'done').length
    const total = tasks.length
    const pct   = total > 0 ? Math.round((done / total) * 100) : 0
    return { label: project.name, value: done, max: total, color: completionColor(pct), sublabel: `${pct}%` }
  })

  const expStatusRows = allProjectData.map(({ project, experiments }) => {
    const planned   = experiments.filter(e => e.status === 'planned').length
    const running   = experiments.filter(e => e.status === 'running').length
    const completed = experiments.filter(e => e.status === 'completed').length
    return {
      label: project.name,
      value: experiments.length,
      max: experiments.length,
      color: '#f59e0b',
      sublabel: String(experiments.length),
      segments: [
        { value: planned,   color: '#f59e0b' },
        { value: running,   color: '#ff8015' },
        { value: completed, color: '#10b981' },
      ],
    }
  })

  const generatedAt = new Date().toLocaleString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>

      {/* ── Header ── */}
      <div style={{
        padding: '0 28px', height: 54,
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'var(--surface-header)', backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            onClick={() => navigate('/projects')}
            style={{
              cursor: 'pointer', background: 'var(--surface-input)',
              border: '1px solid var(--border)', borderRadius: 6,
              color: 'var(--text-muted)', padding: '3px 9px', fontSize: 15, lineHeight: 1,
            }}
          >←</button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <img src="/sabita.jpg" alt="SABITA" style={{ height: 26, borderRadius: 4, display: 'block' }} />
            <span style={{ color: 'var(--text-dim)', fontSize: 13, fontFamily: 'var(--font-mono)' }}>/</span>
            <span style={{ color: '#ff8015', fontSize: 14, fontFamily: 'var(--font-mono)' }}>reports</span>
          </div>
        </div>
        <span style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
          Generated {generatedAt}
        </span>
      </div>

      {/* ── Content ── */}
      <div style={{ maxWidth: 900, margin: '0 auto', padding: '32px 28px 64px' }}>

        {/* Section 1 — Global Summary */}
        <div style={{ marginBottom: 40 }}>
          <SectionHeader title="Global Summary" accent="#ff8015" count={projects.length} />
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <StatCard value={projects.length} label="Total Projects"        accent="#ff8015" />
            <StatCard value={totalDone}       label="Tasks Completed"       accent="#10b981" sublabel={`of ${totalTasks} total`} />
            <StatCard value={totalExps}       label="Total Experiments"     accent="#f59e0b" />
            <StatCard value={runningExps}     label="Running Experiments"   accent="#f43f5e" />
          </div>
        </div>

        {/* Section 2 — Task Completion */}
        <div style={{ marginBottom: 40 }}>
          <SectionHeader title="Task Completion by Project" accent="#ff8015" />
          <div style={{
            background: 'var(--surface-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 8, padding: '20px 24px',
          }}>
            {allProjectData.length === 0 ? (
              <span style={{ color: 'var(--text-dim)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                No data yet
              </span>
            ) : (
              <BarChart rows={taskCompletionRows} rowHeight={28} />
            )}
          </div>
        </div>

        {/* Section 3 — Experiment Status */}
        <div style={{ marginBottom: 40 }}>
          <SectionHeader title="Experiment Status by Project" accent="#10b981" />
          <div style={{
            background: 'var(--surface-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 8, padding: '20px 24px',
          }}>
            {allProjectData.length === 0 ? (
              <span style={{ color: 'var(--text-dim)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                No data yet
              </span>
            ) : (
              <BarChart rows={expStatusRows} rowHeight={28} />
            )}
          </div>
        </div>

        {/* Section 4 — Project Table */}
        <div style={{ marginBottom: 40 }}>
          <SectionHeader title="All Projects" accent="#ff8015" count={projects.length} />
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['PROJECT', 'TASKS', 'EXPERIMENTS', 'MEMBERS', ''].map(h => (
                  <th key={h} style={{
                    padding: '6px 8px', textAlign: 'left',
                    fontSize: 9, fontFamily: 'var(--font-mono)',
                    color: 'var(--text-dim)', letterSpacing: '0.1em',
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {allProjectData.map(({ project, tasks, experiments }) => {
                const done = tasks.filter(t => t.status === 'done').length
                return (
                  <tr key={project.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '10px 8px', color: 'var(--text-heading)', fontWeight: 500 }}>
                      {project.name}
                    </td>
                    <td style={{ padding: '10px 8px', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                      {done}/{tasks.length}
                    </td>
                    <td style={{ padding: '10px 8px', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                      {experiments.length}
                    </td>
                    <td style={{ padding: '10px 8px', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                      {project.members.length}
                    </td>
                    <td style={{ padding: '10px 8px' }}>
                      <button
                        onClick={() => navigate(`/projects/${project.id}/report`)}
                        style={{
                          background: 'rgba(255,128,21,0.08)',
                          border: '1px solid rgba(255,128,21,0.2)',
                          color: '#ff8015', fontFamily: 'var(--font-mono)',
                          fontSize: 9, padding: '3px 8px',
                          borderRadius: 3, cursor: 'pointer', letterSpacing: '0.08em',
                        }}
                      >
                        → VIEW REPORT
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npm run test -- --run src/pages/__tests__/GlobalReportPage.test.tsx
```

Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/frontend/src/pages/GlobalReportPage.tsx \
        EvoScientist/pm/frontend/src/pages/__tests__/GlobalReportPage.test.tsx
git commit -m "feat(report): add GlobalReportPage with cross-project analytics"
```

---

## Task 6: Wire routes and navigation buttons

**Files:**
- Modify: `EvoScientist/pm/frontend/src/main.tsx`
- Modify: `EvoScientist/pm/frontend/src/pages/Board.tsx`
- Modify: `EvoScientist/pm/frontend/src/pages/Projects.tsx`

- [ ] **Step 1: Add routes in main.tsx**

In `src/main.tsx`, add two imports after the existing page imports:

```tsx
import { ProjectReportPage } from './pages/ProjectReportPage'
import { GlobalReportPage }   from './pages/GlobalReportPage'
```

Then add two routes after the `/projects/:id/experiments` route:

```tsx
<Route path="/projects/:id/report" element={<PrivateRoute><ProjectReportPage /></PrivateRoute>} />
<Route path="/reports"             element={<PrivateRoute><GlobalReportPage /></PrivateRoute>} />
```

Full routes block after edit:

```tsx
<Routes>
  {needsSetup && <Route path="*" element={<Setup />} />}
  <Route path="/login"                      element={<Login />} />
  <Route path="/projects"                   element={<PrivateRoute><Projects /></PrivateRoute>} />
  <Route path="/projects/:id"               element={<PrivateRoute><Board /></PrivateRoute>} />
  <Route path="/projects/:id/experiments"   element={<PrivateRoute><ExperimentsPage /></PrivateRoute>} />
  <Route path="/projects/:id/report"        element={<PrivateRoute><ProjectReportPage /></PrivateRoute>} />
  <Route path="/reports"                    element={<PrivateRoute><GlobalReportPage /></PrivateRoute>} />
  <Route path="/profile"                    element={<PrivateRoute><ProfilePage /></PrivateRoute>} />
  {!needsSetup && <Route path="*" element={<Navigate to="/projects" replace />} />}
</Routes>
```

- [ ] **Step 2: Add REPORT button in Board.tsx header**

Find the `⚗ EXPERIMENTS` button in `src/pages/Board.tsx` (around line 456). Add a `📊 REPORT` button immediately after it:

```tsx
<button
  onClick={() => navigate(`/projects/${projectId}/experiments`)}
  style={{
    background: 'rgba(16,185,129,0.08)',
    border: '1px solid rgba(16,185,129,0.18)',
    color: '#64748b',
    fontFamily: 'var(--font-mono)',
    fontSize: 13,
    padding: '4px 10px',
    borderRadius: 4,
    cursor: 'pointer',
    letterSpacing: '0.08em',
  }}
  onMouseEnter={e => { e.currentTarget.style.color = '#10b981'; e.currentTarget.style.borderColor = 'rgba(16,185,129,0.35)' }}
  onMouseLeave={e => { e.currentTarget.style.color = '#64748b'; e.currentTarget.style.borderColor = 'rgba(16,185,129,0.18)' }}
>
  ⚗ EXPERIMENTS
</button>
<button
  onClick={() => navigate(`/projects/${projectId}/report`)}
  style={{
    background: 'rgba(255,128,21,0.08)',
    border: '1px solid rgba(255,128,21,0.18)',
    color: '#64748b',
    fontFamily: 'var(--font-mono)',
    fontSize: 13,
    padding: '4px 10px',
    borderRadius: 4,
    cursor: 'pointer',
    letterSpacing: '0.08em',
  }}
  onMouseEnter={e => { e.currentTarget.style.color = '#ff8015'; e.currentTarget.style.borderColor = 'rgba(255,128,21,0.35)' }}
  onMouseLeave={e => { e.currentTarget.style.color = '#64748b'; e.currentTarget.style.borderColor = 'rgba(255,128,21,0.18)' }}
>
  📊 REPORT
</button>
```

- [ ] **Step 3: Add REPORTS button in Projects.tsx header**

In `src/pages/Projects.tsx`, find the header's `<div>` containing the profile button (around line 264). Add a `📊 REPORTS` button before the profile button:

```tsx
{/* Reports nav button */}
<button
  onClick={() => navigate('/reports')}
  style={{
    background: 'rgba(255,128,21,0.08)',
    border: '1px solid rgba(255,128,21,0.18)',
    color: '#64748b',
    fontFamily: 'var(--font-mono)',
    fontSize: 11,
    padding: '5px 12px',
    borderRadius: 4,
    cursor: 'pointer',
    letterSpacing: '0.08em',
  }}
  onMouseEnter={e => { e.currentTarget.style.color = '#ff8015'; e.currentTarget.style.borderColor = 'rgba(255,128,21,0.35)' }}
  onMouseLeave={e => { e.currentTarget.style.color = '#64748b'; e.currentTarget.style.borderColor = 'rgba(255,128,21,0.18)' }}
>
  📊 REPORTS
</button>
```

The header `justifyContent: 'space-between'` will push the Reports button + profile avatar to the right. Wrap them in a flex div if they need to sit together:

```tsx
{/* right side */}
<div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
  <button onClick={() => navigate('/reports')} style={{ /* as above */ }}>📊 REPORTS</button>
  <button onClick={() => navigate('/profile')} style={{ /* existing profile button style */ }}>
    {username?.[0]?.toUpperCase() ?? '?'}
  </button>
</div>
```

Replace the existing standalone profile button with this wrapper. The profile button's existing style stays unchanged.

- [ ] **Step 4: Build to verify no TypeScript errors**

```bash
cd EvoScientist/pm/frontend
npm run build
```

Expected: `✓ built in ~Xs` with no errors

- [ ] **Step 5: Run full test suite**

```bash
npm run test -- --run
```

Expected: all tests PASS (existing tests must not regress)

- [ ] **Step 6: Commit**

```bash
git add EvoScientist/pm/frontend/src/main.tsx \
        EvoScientist/pm/frontend/src/pages/Board.tsx \
        EvoScientist/pm/frontend/src/pages/Projects.tsx
git commit -m "feat(report): wire report routes and add nav buttons"
```

---

## Task 7: Build, deploy, final verification

- [ ] **Step 1: Build production bundle**

```bash
cd EvoScientist/pm/frontend
npm run build
```

Expected: clean build, new `dist/assets/index-*.js` and `dist/assets/index-*.css`

- [ ] **Step 2: Deploy dist to server**

```bash
tar -czf - dist/ | ssh kaplan@172.20.43.104 \
  "cd /home/kaplan/projects/EvoScientist/EvoScientist/pm/frontend && tar xzf -"
```

- [ ] **Step 3: Restart Docker container**

```bash
ssh kaplan@172.20.43.104 \
  "cd /home/kaplan/projects/EvoScientist && /home/kaplan/.local/bin/docker-compose restart"
```

- [ ] **Step 4: Smoke-test in browser**

Verify:
1. Navigate to Projects page → `📊 REPORTS` button visible in header → click → `/reports` loads with stat cards
2. Open a project board → `📊 REPORT` button visible → click → `/projects/:id/report` loads with all 5 sections
3. Click `⬇ PDF` → browser print dialog opens
4. Expand an experiment accordion in Section 4 → hypothesis + protocol text visible
5. Global report Section 2 bar chart shows one row per project

- [ ] **Step 5: Commit dist**

```bash
cd EvoScientist/pm/frontend
git add dist/
git commit -m "chore: update dist with report module build"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| `StatCard`, `DonutChart`, `BarChart`, `SectionHeader` components | Tasks 1-3 |
| `/projects/:id/report` with sections 1-5 | Task 4 |
| Section 4 expandable accordion | Task 4 |
| PDF export via `window.print()` + `@media print` CSS | Task 4 |
| `/reports` global view with 4 sections | Task 5 |
| Both routes registered + private | Task 6 |
| 📊 REPORT button in Board header | Task 6 |
| 📊 REPORTS button in Projects header | Task 6 |
| Error banner with retry on task query failure | Task 4 |
| Empty donut for 0 tasks | Task 2 (DonutChart handles total=0) |
| Entry counts fetched per experiment via Promise.all | Task 4 |
| Stacked BarChart for experiment status | Tasks 3 + 5 |

All requirements covered. No gaps found.
