import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { EntryEditor } from '../EntryEditor'

describe('EntryEditor', () => {
  it('renders title input and body textarea', () => {
    render(<EntryEditor type="note" onSave={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByPlaceholderText(/title/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/markdown/i)).toBeInTheDocument()
  })

  it('SAVE button is disabled when title is empty', () => {
    render(<EntryEditor type="note" onSave={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByRole('button', { name: /save/i })).toBeDisabled()
  })

  it('SAVE button is enabled when title is non-empty', () => {
    render(<EntryEditor type="result" onSave={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText(/title/i), { target: { value: 'My result' } })
    expect(screen.getByRole('button', { name: /save/i })).not.toBeDisabled()
  })

  it('calls onSave with title and body when submitted', () => {
    const onSave = vi.fn()
    render(<EntryEditor type="note" onSave={onSave} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText(/title/i), { target: { value: 'My Note' } })
    fireEvent.change(screen.getByPlaceholderText(/markdown/i), { target: { value: 'Content here' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    expect(onSave).toHaveBeenCalledWith({ title: 'My Note', body: 'Content here' })
  })

  it('calls onCancel when CANCEL is clicked', () => {
    const onCancel = vi.fn()
    render(<EntryEditor type="note" onSave={vi.fn()} onCancel={onCancel} />)
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onCancel).toHaveBeenCalled()
  })

  it('pre-fills title and body when editing', () => {
    render(
      <EntryEditor type="note" onSave={vi.fn()} onCancel={vi.fn()}
        initialTitle="Existing Title" initialBody="Existing body" />
    )
    expect((screen.getByPlaceholderText(/title/i) as HTMLInputElement).value).toBe('Existing Title')
    expect((screen.getByPlaceholderText(/markdown/i) as HTMLTextAreaElement).value).toBe('Existing body')
  })
})
