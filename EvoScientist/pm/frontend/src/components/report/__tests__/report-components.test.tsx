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
    render(<SectionHeader title="Tasks" />)
    expect(screen.queryByTestId('count-badge')).not.toBeInTheDocument()
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
