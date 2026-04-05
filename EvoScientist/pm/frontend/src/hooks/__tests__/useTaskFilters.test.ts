import { renderHook, act } from '@testing-library/react'
import { describe, test, expect } from 'vitest'
import { useTaskFilters } from '../useTaskFilters'
import { Task } from '../../api'

const TASKS: Task[] = [
  {
    id: '1', project_id: 'p1', title: 'Baseline PCR run',
    priority: 'high', status: 'todo', deadline: '2026-03-01',
    assignee_id: 'u1', description: null, session_id: null,
    created_by: 'u1', created_at: '2026-01-01T00:00:00', updated_at: '2026-01-01T00:00:00',
  },
  {
    id: '2', project_id: 'p1', title: 'Gel electrophoresis',
    priority: 'low', status: 'done', deadline: null,
    assignee_id: null, description: null, session_id: null,
    created_by: 'u1', created_at: '2026-01-02T00:00:00', updated_at: '2026-01-02T00:00:00',
  },
  {
    id: '3', project_id: 'p1', title: 'Western blot protocol',
    priority: 'medium', status: 'in_progress', deadline: '2026-12-31',
    assignee_id: 'u2', description: null, session_id: null,
    created_by: 'u1', created_at: '2026-01-03T00:00:00', updated_at: '2026-01-03T00:00:00',
  },
]

describe('useTaskFilters', () => {
  test('returns all tasks by default', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    expect(result.current.filtered).toHaveLength(3)
  })

  test('filters by search query (case-insensitive)', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    act(() => { result.current.setSearch('pcr') })
    expect(result.current.filtered).toHaveLength(1)
    expect(result.current.filtered[0].id).toBe('1')
  })

  test('empty search returns all tasks', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    act(() => { result.current.setSearch('pcr') })
    act(() => { result.current.setSearch('') })
    expect(result.current.filtered).toHaveLength(3)
  })

  test('filters by priority — deselecting medium and low returns only high', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    act(() => {
      result.current.togglePriority('medium')
      result.current.togglePriority('low')
    })
    expect(result.current.filtered).toHaveLength(1)
    expect(result.current.filtered[0].priority).toBe('high')
  })

  test('deselecting all priorities resets to showing all', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    act(() => {
      result.current.togglePriority('high')
      result.current.togglePriority('medium')
      result.current.togglePriority('low')
    })
    expect(result.current.filtered).toHaveLength(3)
  })

  test('filters by assignee id', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    act(() => { result.current.setAssigneeId('u2') })
    expect(result.current.filtered).toHaveLength(1)
    expect(result.current.filtered[0].id).toBe('3')
  })

  test('assigneeId null returns all', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    act(() => { result.current.setAssigneeId('u1') })
    act(() => { result.current.setAssigneeId(null) })
    expect(result.current.filtered).toHaveLength(3)
  })

  test('sorts by deadline ascending, nulls last', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    act(() => { result.current.setSort('deadline') })
    expect(result.current.filtered[0].id).toBe('1')  // 2026-03-01
    expect(result.current.filtered[1].id).toBe('3')  // 2026-12-31
    expect(result.current.filtered[2].id).toBe('2')  // null → last
  })

  test('sorts by priority: high < medium < low', () => {
    const { result } = renderHook(() => useTaskFilters(TASKS))
    act(() => { result.current.setSort('priority') })
    expect(result.current.filtered[0].priority).toBe('high')
    expect(result.current.filtered[1].priority).toBe('medium')
    expect(result.current.filtered[2].priority).toBe('low')
  })
})
