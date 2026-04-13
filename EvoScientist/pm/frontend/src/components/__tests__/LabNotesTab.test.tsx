// EvoScientist/pm/frontend/src/components/__tests__/LabNotesTab.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, test, expect, vi } from 'vitest'
import { LabNotesTab } from '../task/LabNotesTab'

const COMMENTS = [
  { id: 'c1', body: 'Buffer pH confirmed at 7.4', created_at: '2026-03-01T10:00:00Z' },
  { id: 'c2', body: 'Gel shows expected bands', created_at: '2026-03-02T11:00:00Z' },
]

describe('LabNotesTab', () => {
  test('renders all comments', () => {
    render(
      <LabNotesTab
        comments={COMMENTS}
        commentBody=""
        setCommentBody={vi.fn()}
        onSubmit={vi.fn()}
        isPending={false}
      />
    )
    expect(screen.getByText('Buffer pH confirmed at 7.4')).toBeInTheDocument()
    expect(screen.getByText('Gel shows expected bands')).toBeInTheDocument()
  })

  test('renders empty state when no comments', () => {
    render(
      <LabNotesTab
        comments={[]}
        commentBody=""
        setCommentBody={vi.fn()}
        onSubmit={vi.fn()}
        isPending={false}
      />
    )
    expect(screen.getByText(/no lab notes yet/i)).toBeInTheDocument()
  })

  test('calls setCommentBody on input change', () => {
    const setCommentBody = vi.fn()
    render(
      <LabNotesTab
        comments={[]}
        commentBody=""
        setCommentBody={setCommentBody}
        onSubmit={vi.fn()}
        isPending={false}
      />
    )
    fireEvent.change(screen.getByPlaceholderText(/add a lab note/i), {
      target: { value: 'New observation' },
    })
    expect(setCommentBody).toHaveBeenCalledWith('New observation')
  })

  test('calls onSubmit on form submit', () => {
    const onSubmit = vi.fn()
    render(
      <LabNotesTab
        comments={[]}
        commentBody="test note"
        setCommentBody={vi.fn()}
        onSubmit={onSubmit}
        isPending={false}
      />
    )
    fireEvent.submit(screen.getByRole('form'))
    expect(onSubmit).toHaveBeenCalled()
  })

  test('POST button disabled while isPending', () => {
    render(
      <LabNotesTab
        comments={[]}
        commentBody=""
        setCommentBody={vi.fn()}
        onSubmit={vi.fn()}
        isPending={true}
      />
    )
    expect(screen.getByRole('button', { name: /POST/i })).toBeDisabled()
  })
})
