import { afterEach, describe, expect, test, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AnalyticsPage } from '../AnalyticsPage'

vi.mock('../../auth', () => ({ useAuth: () => ({ token: 't' }) }))

const stats = {
  labs: [{ id: 'l1', name: 'Retina Lab', department: 'Ophthalmology', member_count: 3, members: [] }],
  total_tasks: 12, total_experiments: 4,
  recent_projects: [{ id: 'p1', name: 'OCT study', created_at: '2026-09-01' }],
  task_statuses: { todo: 5 }, experiment_statuses: {}, publication_statuses: {},
  publications_over_time: [],
}

function respond(status: number, body: unknown) {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: status < 400, status, json: async () => body })))
}

describe('AnalyticsPage', () => {
  afterEach(() => vi.unstubAllGlobals())

  test('embedded (Settings → Analytics) renders lab analytics', async () => {
    respond(200, stats)
    render(<AnalyticsPage embedded />)
    expect(await screen.findByText('Retina Lab')).toBeInTheDocument()
    expect(screen.queryByText('Lab Analytics')).toBeNull()  // no page title inside the tab
  })

  test('an error response shows a message instead of crashing', async () => {
    respond(500, { detail: 'boom' })
    render(<AnalyticsPage embedded />)
    expect(await screen.findByText(/Could not load analytics \(HTTP 500\)/)).toBeInTheDocument()
  })

  test('someone who leads no lab gets an explanation, not zeros', async () => {
    respond(200, { ...stats, labs: [], recent_projects: [] })
    render(<AnalyticsPage embedded />)
    expect(await screen.findByText(/You do not lead a lab yet/)).toBeInTheDocument()
  })
})
