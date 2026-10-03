import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MeetingTime } from '../MeetingTime'
import { supervisionApi } from '../../../api'

vi.mock('../../../api', () => ({ supervisionApi: { getMeetingSetting: vi.fn(), setMeetingSetting: vi.fn() } }))

const wrap = (ui: React.ReactNode) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>

describe('MeetingTime', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(supervisionApi.setMeetingSetting).mockResolvedValue({ id: 'm', professor_id: 'p', weekday: 1, time_local: '10:30', timezone: 'Europe/Istanbul', effective_from: '', created_at: '' })
  })

  it('sets the day and time students will see', async () => {
    vi.mocked(supervisionApi.getMeetingSetting).mockResolvedValue(null)
    render(wrap(<MeetingTime week="2026-09-28" />))
    fireEvent.change(screen.getByLabelText('Meeting day'), { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText('Meeting time'), { target: { value: '10:30' } })
    fireEvent.click(screen.getByRole('button', { name: 'Set meeting time' }))
    await waitFor(() => expect(supervisionApi.setMeetingSetting).toHaveBeenCalledWith(1, '10:30', 'Europe/Istanbul'))
  })

  it('shows the current setting and only enables saving after a change', async () => {
    vi.mocked(supervisionApi.getMeetingSetting).mockResolvedValue({ id: 'm', professor_id: 'p', weekday: 4, time_local: '15:00', timezone: null, effective_from: '', created_at: '' })
    render(wrap(<MeetingTime week="2026-09-28" />))
    await waitFor(() => expect((screen.getByLabelText('Meeting day') as HTMLSelectElement).value).toBe('4'))
    expect(screen.getByRole('button', { name: 'Change' })).toBeDisabled()
  })
})
