// EvoScientist/pm/frontend/src/components/board/__tests__/BulkActionBar.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi } from 'vitest'
import { BulkActionBar } from '../BulkActionBar'

const PHASES = [
  { id: 'ph1', name: 'Phase 1' },
  { id: 'ph2', name: 'Phase 2' },
]

describe('BulkActionBar', () => {
  test('renders selected count', () => {
    render(
      <BulkActionBar
        count={3}
        phases={PHASES}
        onStatusChange={vi.fn()}
        onPhaseChange={vi.fn()}
        onClear={vi.fn()}
      />
    )
    expect(screen.getByText(/3 selected/i)).toBeInTheDocument()
  })

  test('status dropdown calls onStatusChange with chosen value', () => {
    const onStatusChange = vi.fn()
    render(
      <BulkActionBar
        count={2}
        phases={PHASES}
        onStatusChange={onStatusChange}
        onPhaseChange={vi.fn()}
        onClear={vi.fn()}
      />
    )
    fireEvent.change(screen.getByTestId('bulk-status-select'), {
      target: { value: 'done' },
    })
    expect(onStatusChange).toHaveBeenCalledWith('done')
  })

  test('phase dropdown calls onPhaseChange with phase id', () => {
    const onPhaseChange = vi.fn()
    render(
      <BulkActionBar
        count={2}
        phases={PHASES}
        onStatusChange={vi.fn()}
        onPhaseChange={onPhaseChange}
        onClear={vi.fn()}
      />
    )
    fireEvent.change(screen.getByTestId('bulk-phase-select'), {
      target: { value: 'ph1' },
    })
    expect(onPhaseChange).toHaveBeenCalledWith('ph1')
  })

  test('phase dropdown calls onPhaseChange with null when No phase is selected', () => {
    const onPhaseChange = vi.fn()
    render(
      <BulkActionBar
        count={2}
        phases={PHASES}
        onStatusChange={vi.fn()}
        onPhaseChange={onPhaseChange}
        onClear={vi.fn()}
      />
    )
    fireEvent.change(screen.getByTestId('bulk-phase-select'), {
      target: { value: '__none__' },
    })
    expect(onPhaseChange).toHaveBeenCalledWith(null)
  })

  test('clear button calls onClear', () => {
    const onClear = vi.fn()
    render(
      <BulkActionBar
        count={2}
        phases={PHASES}
        onStatusChange={vi.fn()}
        onPhaseChange={vi.fn()}
        onClear={onClear}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /clear/i }))
    expect(onClear).toHaveBeenCalled()
  })
})
