import { useMemo, useState } from 'react'
import { Task } from '../api'

export type SortKey = 'created' | 'deadline' | 'priority'
export type PrioritySet = Set<Task['priority']>

const ALL_PRIORITIES: Task['priority'][] = ['high', 'medium', 'low']
const PRIORITY_ORDER: Record<Task['priority'], number> = { high: 0, medium: 1, low: 2 }

export function useTaskFilters(tasks: Task[]) {
  const [search, setSearch] = useState('')
  const [priorities, setPriorities] = useState<PrioritySet>(new Set(ALL_PRIORITIES))
  const [sort, setSort] = useState<SortKey>('created')
  const [assigneeId, setAssigneeId] = useState<string | null>(null)

  const filtered = useMemo(() => {
    let result = tasks

    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(t => t.title.toLowerCase().includes(q))
    }

    if (priorities.size < ALL_PRIORITIES.length) {
      result = result.filter(t => priorities.has(t.priority))
    }

    if (assigneeId !== null) {
      result = result.filter(t => t.assignee_id === assigneeId)
    }

    return [...result].sort((a, b) => {
      if (sort === 'priority') {
        return PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]
      }
      if (sort === 'deadline') {
        if (!a.deadline && !b.deadline) return 0
        if (!a.deadline) return 1
        if (!b.deadline) return -1
        return a.deadline.localeCompare(b.deadline)
      }
      // default: created
      return a.created_at.localeCompare(b.created_at)
    })
  }, [tasks, search, priorities, sort, assigneeId])

  function togglePriority(p: Task['priority']) {
    setPriorities(prev => {
      const next = new Set(prev)
      if (next.has(p)) {
        next.delete(p)
      } else {
        next.add(p)
      }
      return next.size === 0 ? new Set(ALL_PRIORITIES) : next
    })
  }

  return { search, setSearch, priorities, togglePriority, sort, setSort, assigneeId, setAssigneeId, filtered }
}
