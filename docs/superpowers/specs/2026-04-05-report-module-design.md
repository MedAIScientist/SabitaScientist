# Report Module Design

## Goal

Add a Reports module to the EvoScientist PM frontend that gives researchers structured visibility into project progress and experiment outcomes, at both per-project and cross-project level, with PDF export.

## Architecture

Two new route-level pages share a set of small, focused report components. Charts are hand-rolled SVG — no new npm dependencies. PDF export uses `window.print()` with `@media print` CSS.

**Tech stack:** React + TypeScript, TanStack Query (already installed), pure SVG charts, browser print API.

---

## File Structure

### New files

```
src/pages/
  ProjectReportPage.tsx       # /projects/:id/report
  GlobalReportPage.tsx        # /reports

src/components/report/
  StatCard.tsx                # single metric: large value + label + accent border
  DonutChart.tsx              # SVG donut via stroke-dasharray, multi-segment
  BarChart.tsx                # SVG horizontal bar rows with labels
  SectionHeader.tsx           # mono uppercase heading with left accent bar
```

### Modified files

```
src/main.tsx                  # add two new routes
src/pages/Board.tsx           # add 📊 REPORT button in header
src/pages/Projects.tsx        # add 📊 REPORTS button in header
```

---

## Routes

| Path | Component | Description |
|------|-----------|-------------|
| `/projects/:id/report` | `ProjectReportPage` | Per-project detailed report |
| `/reports` | `GlobalReportPage` | Cross-project analytics |

Both routes are private (require auth), consistent with existing route pattern in `main.tsx`.

---

## Per-Project Report (`ProjectReportPage`)

### Data fetched

- `api.getProject(projectId)` — project metadata + members
- `api.listTasks(projectId)` — all tasks
- `api.listExperiments(projectId)` — all experiments
- Per experiment: `api.listEntries(projectId, expId)` — entry counts (notes + results)

Entry counts are fetched in parallel using `Promise.all` after experiments load, stored in a `Map<expId, {notes: number, results: number}>`.

### Layout

**Sticky header** (same style as Board/ExperimentsPage):
- ← back button → `/projects/:id`
- SABITA logo + `/` + project name + `/ report`
- `⬇ PDF` button (right side) — calls `window.print()`

**Section 1 — Summary** (4 `StatCard` components in a row):
- Total Tasks
- Done % (done / total × 100, rounded)
- Total Experiments
- Team Members

**Section 2 — Task Breakdown**:
- `DonutChart` with 3 segments: todo (`#ff8015`), in_progress (`#f59e0b`), done (`#10b981`)
- Counts legend beside chart: label + count + percentage
- Priority breakdown table: High / Medium / Low rows, columns: Count | % of Total

**Section 3 — Experiment Overview**:
- `DonutChart` with 3 segments: planned (`#f59e0b`), running (`#ff8015`), completed (`#10b981`)
- Experiment table: Name | Status badge | Tags | Deadline | Notes | Results — sorted by status

**Section 4 — Experiment Details** (expandable accordion rows):
- Each row: experiment name + status badge
- Expanded: hypothesis snippet (first 200 chars), protocol snippet (first 200 chars), note count, result count
- Collapsed by default, click to expand

**Section 5 — Team Activity**:
- One row per member: avatar circle | username | role badge | tasks assigned | tasks completed

### PDF export

`@media print` block (injected as a `<style>` tag in the component):
- Hide header buttons, nav elements
- Remove background colors, use white background
- Expand all accordion rows
- A4 page size, 20mm margins
- Page break before Section 3 and Section 5

---

## Global Report (`GlobalReportPage`)

### Data fetched

- `api.listProjects()` — all projects the user has access to
- Per project (parallel): `api.listTasks(id)`, `api.listExperiments(id)`

All per-project fetches run in parallel via individual `useQuery` calls inside a `GlobalProjectRow` sub-component (same pattern as `ProjectCard` on the Projects page).

### Layout

**Sticky header**:
- ← back button → `/projects`
- SABITA logo + `/ reports`
- Generation timestamp (right side)

**Section 1 — Global Summary** (4 `StatCard` components):
- Total Projects
- Tasks Completed (sum of done tasks across all projects)
- Total Experiments
- Running Experiments (status = 'running')

**Section 2 — Task Completion by Project** (`BarChart`):
- One horizontal bar row per project
- Bar value = done / total tasks (%)
- Color: red (`#f43f5e`) if < 30%, amber (`#f59e0b`) if 30–69%, green (`#10b981`) if ≥ 70%
- Shows percentage label at end of bar

**Section 3 — Experiment Status by Project** (`BarChart`):
- One horizontal bar row per project
- Stacked segments: planned (amber) | running (orange) | completed (green)
- Shows total experiment count as label

**Section 4 — Project Summary Table**:
- Columns: Project Name | Tasks Done/Total | Experiments | Members | → VIEW REPORT (link)

---

## Shared Components

### `StatCard`

Props: `value: string | number`, `label: string`, `accent: string`, `sublabel?: string`

Renders a card with:
- Large bold `value` in `var(--text-heading)`
- Small mono `label` in `var(--text-dim)`
- 3px left border in `accent` color
- Optional `sublabel` (e.g. "of 12 total") below value in dim text

### `DonutChart`

Props: `segments: { value: number; color: string; label: string }[]`, `size?: number` (default 120), `strokeWidth?: number` (default 18)

Implementation:
- Single SVG `viewBox="0 0 {size} {size}"`
- One `<circle>` per segment, `cx`/`cy` at center, `r = (size - strokeWidth) / 2`
- `circumference = 2π × r`
- Each segment: `stroke-dasharray = portion × circumference, circumference`, `stroke-dashoffset` rotated to start after previous segments
- `transform="rotate(-90, cx, cy)"` to start at top
- Center text: largest segment label

### `BarChart`

Props: `rows: { label: string; value: number; max: number; color: string; sublabel?: string }[]`, `height?: number` (default 28 per row)

Implementation:
- SVG with dynamic height (`rows.length × (height + gap)`)
- Per row: `<text>` label (left, fixed width 140px), `<rect>` background bar (light), `<rect>` value bar (colored), `<text>` value label (right of bar)
- For stacked bars: `rows` entry has `segments: { value: number; color: string }[]` instead of single `value`/`color`. The component checks for the presence of `segments` to switch rendering mode.

### `SectionHeader`

Props: `title: string`, `accent?: string` (default `#ff8015`), `count?: number`

Renders: uppercase mono heading with 2px left border in accent color, optional count badge.

---

## Navigation Entry Points

### Board header

Add button between `⚗ EXPERIMENTS` and `⚙ SETTINGS`:

```tsx
<button onClick={() => navigate(`/projects/${projectId}/report`)}>
  📊 REPORT
</button>
```

Style matches the existing `⚗ EXPERIMENTS` button (green accent → use orange accent for report).

### Projects page header

Add button in the top-right actions area:

```tsx
<button onClick={() => navigate('/reports')}>
  📊 REPORTS
</button>
```

---

## Data Constraints

- All data is fetched client-side from existing API endpoints — no new backend routes needed.
- Entry counts require one `api.listEntries` call per experiment. For projects with many experiments this could be slow; the UI shows a loading spinner per experiment row while counts load.
- `GlobalReportPage` fetches all projects then all tasks/experiments per project in parallel. With many projects (>20), this is acceptable for an internal research tool.

---

## Error Handling

- If any query fails, show an inline error message in the affected section ("Could not load task data — please retry") with a retry button that calls `refetch()`.
- Empty states: if a project has 0 tasks, the task donut shows a grey placeholder circle with "No tasks yet".

---

## Print CSS

```css
@media print {
  .no-print { display: none !important; }
  body { background: white !important; color: black !important; }
  .report-section { break-inside: avoid; }
  .report-section--experiments { break-before: page; }
  .report-section--team { break-before: page; }
  .accordion-body { display: block !important; }
}
```

Applied via a `<style>` tag rendered inside the report component (scoped to print media).
