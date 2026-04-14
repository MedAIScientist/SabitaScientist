// EvoScientist/pm/frontend/src/components/board/__tests__/DraggableCard.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi } from 'vitest'

vi.mock('@dnd-kit/core', () => ({
  useDraggable: () => ({ attributes: {}, listeners: {}, setNodeRef: () => {}, transform: null }),
}))
vi.mock('@dnd-kit/utilities', () => ({
  CSS: { Transform: { toString: () => '' } },
}))

import { DraggableCard } from '../DraggableCard'
import type { Task } from '../../../api'

const COL = {
  key: 'todo',
  label: 'PLANNED',
  accent: '#ff8015',
  glow: '255,128,21',
}

const TASK: Task = {
  id: 'task-1', project_id: 'proj-1',
  title: 'Design primer sequences',
  description: null, assignee_id: null,
  status: 'todo', priority: 'high',
  deadline: null, session_id: null,
  created_by: 'u1', created_at: '2026-01-01', updated_at: '2026-01-01',
}

describe('DraggableCard checkbox', () => {
  test('checkbox visible and checked when isSelected=true', () => {
    render(
      <DraggableCard
        task={TASK} col={COL} idx={0} activeTaskId={null}
        onCardClick={vi.fn()} onEditClick={vi.fn()} members={[]}
        isSelected={true} onToggleSelect={vi.fn()}
      />
    )
    expect(screen.getByRole('checkbox')).toBeInTheDocument()
    expect(screen.getByRole('checkbox')).toBeChecked()
  })

  test('checkbox appears on hover when not selected', () => {
    const { container } = render(
      <DraggableCard
        task={TASK} col={COL} idx={0} activeTaskId={null}
        onCardClick={vi.fn()} onEditClick={vi.fn()} members={[]}
        isSelected={false} onToggleSelect={vi.fn()}
      />
    )
    const card = container.querySelector('[data-card="true"]') as HTMLElement
    expect(screen.queryByRole('checkbox')).toBeNull()
    fireEvent.mouseEnter(card)
    expect(screen.getByRole('checkbox')).toBeInTheDocument()
  })

  test('clicking checkbox calls onToggleSelect with task id', () => {
    const onToggleSelect = vi.fn()
    render(
      <DraggableCard
        task={TASK} col={COL} idx={0} activeTaskId={null}
        onCardClick={vi.fn()} onEditClick={vi.fn()} members={[]}
        isSelected={true} onToggleSelect={onToggleSelect}
      />
    )
    fireEvent.click(screen.getByRole('checkbox'))
    expect(onToggleSelect).toHaveBeenCalledWith('task-1')
  })

  test('clicking checkbox does NOT call onCardClick', () => {
    const onCardClick = vi.fn()
    render(
      <DraggableCard
        task={TASK} col={COL} idx={0} activeTaskId={null}
        onCardClick={onCardClick} onEditClick={vi.fn()} members={[]}
        isSelected={true} onToggleSelect={vi.fn()}
      />
    )
    fireEvent.click(screen.getByRole('checkbox'))
    expect(onCardClick).not.toHaveBeenCalled()
  })
})
