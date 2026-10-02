import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { WeekPicker, mondayOf, ymd } from '../../components/supervision/WeekPicker'

describe('WeekPicker', () => {
  it('finds the Monday, including from a Sunday', () => {
    expect(ymd(mondayOf(new Date(2026, 9, 4)))).toBe('2026-09-28') // Sun Oct 4 -> Mon Sep 28
    expect(ymd(mondayOf(new Date(2026, 8, 28)))).toBe('2026-09-28')
  })

  it('marks the selected week and picks another on click', () => {
    const onChange = vi.fn()
    render(<WeekPicker value="2026-09-28" onChange={onChange} />)
    expect(screen.getByLabelText('Week of 2026-09-28').getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(screen.getByLabelText('Week of 2026-09-14'))
    expect(onChange).toHaveBeenCalledWith('2026-09-14')
  })
})
