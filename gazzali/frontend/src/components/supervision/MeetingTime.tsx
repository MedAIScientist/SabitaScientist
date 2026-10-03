import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { supervisionApi } from '../../api'

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

/** The professor's weekly meeting slot; students see it on their dashboard. */
export function MeetingTime({ week }: { week: string }) {
  const qc = useQueryClient()
  const { data: current } = useQuery({ queryKey: ['meeting-setting', week], queryFn: () => supervisionApi.getMeetingSetting(week) })
  const [weekday, setWeekday] = useState(3)
  const [time, setTime] = useState('14:00')
  useEffect(() => {
    if (current) {
      setWeekday(current.weekday)
      if (current.time_local) setTime(current.time_local)
    }
  }, [current])
  const save = useMutation({
    mutationFn: () => supervisionApi.setMeetingSetting(weekday, time, 'Europe/Istanbul'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['meeting-setting'] }),
  })
  const changed = !current || current.weekday !== weekday || (current.time_local ?? '') !== time

  return (
    <section aria-label="Weekly meeting time" style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12, marginBottom: 14 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-dim)', marginBottom: 6 }}>Weekly meeting time</div>
      <div style={{ display: 'flex', gap: 6 }}>
        <select className="input" aria-label="Meeting day" value={weekday} onChange={e => setWeekday(Number(e.target.value))} style={{ flex: 1 }}>
          {WEEKDAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
        </select>
        <input className="input" aria-label="Meeting time" type="time" value={time} onChange={e => setTime(e.target.value)} style={{ width: 110 }} />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
        <button className="btn btn-primary" disabled={!changed || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? 'Saving…' : current ? 'Change' : 'Set meeting time'}
        </button>
        <span style={{ fontSize: 12, color: 'var(--text-3)' }}>
          {save.isSuccess && !changed ? 'Saved. ' : ''}Your students see it on their home page.
        </span>
      </div>
      {save.isError && <div className="msg msg-error" role="alert">{(save.error as Error).message}</div>}
    </section>
  )
}
