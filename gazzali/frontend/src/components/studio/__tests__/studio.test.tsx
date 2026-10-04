import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SectionEditor } from '../SectionEditor'
import { kindLabel, nextStep, progress } from '../studioSteps'
import { api, type Version } from '../../../api'

vi.mock('../../../api', () => ({ api: { getVersion: vi.fn(), saveSectionText: vi.fn() } }))

describe('studio steps', () => {
  it('picks the first unfinished step and counts progress', () => {
    expect(nextStep({ setup: true, evidence: true })?.key).toBe('outline')
    expect(nextStep({ setup: true, evidence: true, outline: true, sections: true, coherence: true, integrity: true, submit: true })).toBeNull()
    expect(progress({ setup: true, evidence: true })).toEqual({ done: 2, total: 7 })
    expect(kindLabel('tasks', 3)).toBe('Tasks')
    expect(kindLabel('metrics', 1)).toBe('Measured result')
  })
})

describe('SectionEditor', () => {
  it('lets the author edit the AI draft and saves it as their own version', async () => {
    const v = { id: 'v1', version: 1, section: 'introduction', generated_by: 'ai-agent', content_length: 20, created_at: '2026-10-04' } as Version
    vi.mocked(api.getVersion).mockResolvedValue({ ...v, content: 'AI wrote this intro.' })
    vi.mocked(api.saveSectionText).mockResolvedValue({ ...v, id: 'v2', version: 2, generated_by: 'human' })
    render(<QueryClientProvider client={new QueryClient()}>
      <SectionEditor pubId="p" section="introduction" claims={[]} versions={[v]} onDraft={() => {}} drafting={false} canDraft />
    </QueryClientProvider>)
    expect(await screen.findByText('AI wrote this intro.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    fireEvent.change(screen.getByLabelText('introduction text'), { target: { value: 'My revised intro.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save my revision' }))
    await waitFor(() => expect(api.saveSectionText).toHaveBeenCalledWith('p', 'introduction', 'My revised intro.'))
    expect(screen.getByRole('button', { name: 'Redraft with AI' })).toBeInTheDocument()
  })
})
