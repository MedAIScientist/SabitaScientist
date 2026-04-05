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
import { DonutChart } from '../DonutChart'

describe('DonutChart', () => {
  it('renders an SVG element', () => {
    const { container } = render(
      <DonutChart segments={[
        { value: 3, color: '#ff8015', label: 'PLANNED' },
        { value: 5, color: '#10b981', label: 'DONE' },
      ]} />
    )
    expect(container.querySelector('svg')).toBeInTheDocument()
  })

  it('renders one circle per segment', () => {
    const { container } = render(
      <DonutChart segments={[
        { value: 3, color: '#ff8015', label: 'A' },
        { value: 5, color: '#10b981', label: 'B' },
      ]} />
    )
    expect(container.querySelectorAll('circle').length).toBe(2)
  })

  it('renders empty state circle when total is 0', () => {
    const { container } = render(
      <DonutChart segments={[{ value: 0, color: '#ff8015', label: 'NONE' }]} />
    )
    expect(container.querySelectorAll('circle').length).toBe(1)
  })

  it('shows label of largest segment in center', () => {
    render(
      <DonutChart segments={[
        { value: 2, color: '#ff8015', label: 'SMALL' },
        { value: 8, color: '#10b981', label: 'BIG' },
      ]} />
    )
    expect(screen.getByText('BIG')).toBeInTheDocument()
  })
})
