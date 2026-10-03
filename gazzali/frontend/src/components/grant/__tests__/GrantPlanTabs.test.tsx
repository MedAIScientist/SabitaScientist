import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi, beforeEach } from 'vitest'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { GrantBudgetTab } from '../GrantBudgetTab'
import { GrantMilestonesTab } from '../GrantMilestonesTab'

vi.mock('@tanstack/react-query', () => ({
  useMutation: vi.fn(),
  useQuery: vi.fn(),
  useQueryClient: vi.fn(),
}))
vi.mock('../../api', () => ({
  api: {
    listGrantBudget: vi.fn(),
    createGrantBudgetItem: vi.fn(),
    updateGrantBudgetItem: vi.fn(),
    deleteGrantBudgetItem: vi.fn(),
    listGrantMilestones: vi.fn(),
    createGrantMilestone: vi.fn(),
    updateGrantMilestone: vi.fn(),
    deleteGrantMilestone: vi.fn(),
    listGrantMembers: vi.fn(),
    searchUsers: vi.fn(() => Promise.resolve([])),
  },
  GRANT_BUDGET_CATEGORIES: ['personnel', 'equipment', 'consumables', 'travel', 'services', 'other'],
  GRANT_MILESTONE_KINDS: ['milestone', 'report', 'deliverable'],
}))

const mockedUseQuery = vi.mocked(useQuery)
const mockedUseMutation = vi.mocked(useMutation)
const mockedUseQueryClient = vi.mocked(useQueryClient)

beforeEach(() => {
  mockedUseQueryClient.mockReturnValue({ invalidateQueries: vi.fn() } as any)
  mockedUseMutation.mockReturnValue({ mutate: vi.fn(), isPending: false } as any)
})

const budgetItem = {
  id: 'b1', grant_id: 'g1', category: 'equipment' as const,
  description: 'Sequencer', planned_amount: 1000, spent_amount: 400,
  position: 0, created_at: '2026-01-01', updated_at: '2026-01-01',
}

describe('GrantBudgetTab', () => {
  test('shows planned, spent and remaining totals', () => {
    mockedUseQuery.mockReturnValue({ data: [budgetItem], isLoading: false } as any)
    render(<GrantBudgetTab grantId="g1" currency="TRY" canEdit />)

    // 1000 planned, 400 spent, 600 remaining
    expect(screen.getByText(/^1,000 TRY$/i)).toBeInTheDocument()
    expect(screen.getByText(/^400 TRY$/i)).toBeInTheDocument()
    expect(screen.getByText(/^600 TRY$/i)).toBeInTheDocument()
    expect(screen.getByText(/^40% OF BUDGET SPENT$/i)).toBeInTheDocument()
    expect(screen.getByText(/^EQUIPMENT$/i)).toBeInTheDocument()
    expect(screen.getByText('Sequencer')).toBeInTheDocument()
  })

  test('flags an overspent budget', () => {
    mockedUseQuery.mockReturnValue({
      data: [{ ...budgetItem, planned_amount: 100, spent_amount: 250 }],
      isLoading: false,
    } as any)
    render(<GrantBudgetTab grantId="g1" currency="TRY" canEdit />)
    expect(screen.getByText(/OVER BUDGET/i)).toBeInTheDocument()
  })

  test('a reader gets no add or edit affordances', () => {
    mockedUseQuery.mockReturnValue({ data: [budgetItem], isLoading: false } as any)
    render(<GrantBudgetTab grantId="g1" currency="TRY" canEdit={false} />)
    expect(screen.queryByText(/^\+ ADD BUDGET LINE$/i)).toBeNull()
    expect(screen.queryByText(/^EDIT$/i)).toBeNull()
    expect(screen.queryByText(/^DELETE$/i)).toBeNull()
  })

  test('an editor can reveal the add-line form', () => {
    mockedUseQuery.mockReturnValue({ data: [], isLoading: false } as any)
    render(<GrantBudgetTab grantId="g1" currency="TRY" canEdit />)
    fireEvent.click(screen.getByText(/^\+ ADD BUDGET LINE$/i))
    expect(screen.getByText(/^CATEGORY$/i)).toBeInTheDocument()
    expect(screen.getByText(/^ADD LINE$/i)).toBeInTheDocument()
  })
})

const milestone = {
  id: 'm1', grant_id: 'g1', title: 'Interim report', kind: 'report' as const,
  due_date: '2020-01-01', completed_at: null, owner_id: null,
  notes: null, position: 0, created_at: '2026-01-01', updated_at: '2026-01-01',
}

describe('GrantMilestonesTab', () => {
  test('marks a past-due open item as overdue', () => {
    mockedUseQuery
      .mockReturnValueOnce({ data: [milestone], isLoading: false } as any)
      .mockReturnValueOnce({ data: [], isLoading: false } as any)
    render(<GrantMilestonesTab grantId="g1" canEdit />)
    expect(screen.getByText('Interim report')).toBeInTheDocument()
    // the row itself is flagged, and the header counts it
    expect(screen.getByText(/^DUE 2020\-01\-01 · OVERDUE$/i)).toBeInTheDocument()
    expect(screen.getByText(/1 OVERDUE/i)).toBeInTheDocument()
  })

  test('a completed item is not overdue', () => {
    mockedUseQuery
      .mockReturnValueOnce({
        data: [{ ...milestone, completed_at: '2020-02-01T10:00:00Z' }],
        isLoading: false,
      } as any)
      .mockReturnValueOnce({ data: [], isLoading: false } as any)
    render(<GrantMilestonesTab grantId="g1" canEdit />)
    expect(screen.queryByText(/OVERDUE/i)).toBeNull()
    expect(screen.getByText(/DONE 2020-02-01/i)).toBeInTheDocument()
  })

  test('ticking the checkbox completes the item', () => {
    const mutate = vi.fn()
    mockedUseMutation.mockReturnValue({ mutate, isPending: false } as any)
    mockedUseQuery
      .mockReturnValueOnce({ data: [milestone], isLoading: false } as any)
      .mockReturnValueOnce({ data: [], isLoading: false } as any)
    render(<GrantMilestonesTab grantId="g1" canEdit />)

    fireEvent.click(screen.getByRole('checkbox'))
    expect(mutate).toHaveBeenCalledWith({ id: 'm1', completed: true })
  })

  test('a reader cannot tick or delete', () => {
    mockedUseQuery
      .mockReturnValueOnce({ data: [milestone], isLoading: false } as any)
      .mockReturnValueOnce({ data: [], isLoading: false } as any)
    render(<GrantMilestonesTab grantId="g1" canEdit={false} />)
    expect(screen.getByRole('checkbox')).toBeDisabled()
    expect(screen.queryByText(/^DELETE$/i)).toBeNull()
    expect(screen.queryByText(/^\+ ADD$/i)).toBeNull()
  })
})
