import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi } from 'vitest'
import { FilterToolbar } from '../FilterToolbar'
import { Task, Member } from '../../api'
import { PrioritySet, SortKey } from '../../hooks/useTaskFilters'

const MEMBERS: Member[] = [
  { user_id: 'u1', username: 'alice', role: 'member', added_at: '2026-01-01' },
  { user_id: 'u2', username: 'bob', role: 'admin', added_at: '2026-01-01' },
]

const ALL_PRIORITIES: PrioritySet = new Set(['high', 'medium', 'low'] as Task['priority'][])

function defaultProps(overrides = {}) {
  return {
    search: '',
    onSearchChange: vi.fn(),
    priorities: ALL_PRIORITIES,
    onTogglePriority: vi.fn(),
    sort: 'created' as SortKey,
    onSortChange: vi.fn(),
    assigneeId: null,
    onAssigneeChange: vi.fn(),
    members: MEMBERS,
    ...overrides,
  }
}

describe('FilterToolbar', () => {
  test('renders search input with lab placeholder', () => {
    render(<FilterToolbar {...defaultProps()} />)
    const input = screen.getByPlaceholderText('🔬 Search experiments…')
    expect(input).toBeInTheDocument()
  })

  test('renders CRIT, NORM, ROUT priority chips', () => {
    render(<FilterToolbar {...defaultProps()} />)
    expect(screen.getByRole('button', { name: 'CRIT' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'NORM' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'ROUT' })).toBeInTheDocument()
  })

  test('calls onSearchChange when typing in search', () => {
    const onSearchChange = vi.fn()
    render(<FilterToolbar {...defaultProps({ onSearchChange })} />)
    const input = screen.getByPlaceholderText('🔬 Search experiments…')
    fireEvent.change(input, { target: { value: 'pcr' } })
    expect(onSearchChange).toHaveBeenCalledWith('pcr')
  })

  test('calls onTogglePriority("high") when CRIT chip clicked', () => {
    const onTogglePriority = vi.fn()
    render(<FilterToolbar {...defaultProps({ onTogglePriority })} />)
    fireEvent.click(screen.getByRole('button', { name: 'CRIT' }))
    expect(onTogglePriority).toHaveBeenCalledWith('high')
  })

  test('calls onTogglePriority("medium") when NORM chip clicked', () => {
    const onTogglePriority = vi.fn()
    render(<FilterToolbar {...defaultProps({ onTogglePriority })} />)
    fireEvent.click(screen.getByRole('button', { name: 'NORM' }))
    expect(onTogglePriority).toHaveBeenCalledWith('medium')
  })

  test('calls onTogglePriority("low") when ROUT chip clicked', () => {
    const onTogglePriority = vi.fn()
    render(<FilterToolbar {...defaultProps({ onTogglePriority })} />)
    fireEvent.click(screen.getByRole('button', { name: 'ROUT' }))
    expect(onTogglePriority).toHaveBeenCalledWith('low')
  })

  test('renders "All" + member names in assignee dropdown', () => {
    render(<FilterToolbar {...defaultProps()} />)
    expect(screen.getByRole('option', { name: 'All' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'alice' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'bob' })).toBeInTheDocument()
  })

  test('calls onAssigneeChange(null) when "All" selected in assignee dropdown', () => {
    const onAssigneeChange = vi.fn()
    render(<FilterToolbar {...defaultProps({ assigneeId: 'u1', onAssigneeChange })} />)
    const select = screen.getByDisplayValue('alice')
    fireEvent.change(select, { target: { value: '' } })
    expect(onAssigneeChange).toHaveBeenCalledWith(null)
  })
})
