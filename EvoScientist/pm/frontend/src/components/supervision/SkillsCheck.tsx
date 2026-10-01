import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { supervisionApi, SkillAssessment } from '../../api'

/**
 * Semester skills check. Shows the student's self-assessment next to the
 * supervisor's for every term (a trend), and lets the viewer rate the current term
 * from their own perspective — "self" for the student, "supervisor" otherwise.
 */
export function SkillsCheck({ studentId, perspective }: { studentId: string; perspective: 'self' | 'supervisor' }) {
  const qc = useQueryClient()
  const { data: view } = useQuery({ queryKey: ['skills', studentId], queryFn: () => supervisionApi.getSkills(studentId) })
  const mine = view?.assessments.find(a => a.term === view.current_term && a.perspective === perspective)
  const [scores, setScores] = useState<Record<string, number>>({})
  const [comment, setComment] = useState('')
  useEffect(() => { setScores(mine?.scores ?? {}); setComment(mine?.comment ?? '') }, [mine?.updated_at])
  const save = useMutation({
    mutationFn: () => supervisionApi.saveSkills(studentId, scores, comment || undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skills', studentId] }),
  })
  if (!view) return null

  const terms = [...new Set(view.assessments.map(a => a.term))]
  const cell = (term: string, p: SkillAssessment['perspective'], skill: string) =>
    view.assessments.find(a => a.term === term && a.perspective === p)?.scores[skill]

  return (
    <section className="request" aria-label="Skills check">
      <div className="request-title" style={{ marginBottom: 4 }}>Skills check · {view.current_term}</div>
      <p className="hint" style={{ marginBottom: 10 }}>
        {perspective === 'self' ? 'Rate yourself once per semester; your supervisor rates you too.' : 'Your rating appears next to the student’s self-assessment.'}
        {' '}1 {view.levels['1']} · 2 {view.levels['2']} · 3 {view.levels['3']} · 4 {view.levels['4']}
      </p>
      <div style={{ overflowX: 'auto' }}>
        <table className="bucket-table">
          <thead>
            <tr>
              <th>Skill</th>
              {terms.map(t => <th key={t} colSpan={2} style={{ textAlign: 'center' }}>{t}</th>)}
              <th>Your rating now</th>
            </tr>
            {terms.length > 0 && (
              <tr><th />{terms.map(t => [<th key={t + 's'} className="hint">self</th>, <th key={t + 'v'} className="hint">supervisor</th>])}<th /></tr>
            )}
          </thead>
          <tbody>
            {Object.entries(view.skills).map(([key, label]) => (
              <tr key={key}>
                <td>{label}</td>
                {terms.map(t => [
                  <td key={t + 's'} style={{ textAlign: 'center' }}>{cell(t, 'self', key) ?? '—'}</td>,
                  <td key={t + 'v'} style={{ textAlign: 'center' }}>{cell(t, 'supervisor', key) ?? '—'}</td>,
                ])}
                <td>
                  <div className="seg" role="radiogroup" aria-label={label} style={{ height: 28 }}>
                    {[1, 2, 3, 4].map(n => (
                      <button key={n} type="button" aria-pressed={scores[key] === n} title={view.levels[String(n)]}
                        onClick={() => setScores(s => ({ ...s, [key]: n }))}>{n}</button>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
        <input className="input" placeholder={perspective === 'self' ? 'What you want to improve (optional)' : 'Comment for the student (optional)'}
          value={comment} onChange={e => setComment(e.target.value)} />
        <button className="btn btn-primary" disabled={save.isPending || Object.keys(scores).length === 0} onClick={() => save.mutate()}>
          {save.isPending ? 'Saving…' : mine ? 'Update' : 'Save'}
        </button>
      </div>
      {view.assessments.filter(a => a.comment).slice(-2).map(a => (
        <p key={a.term + a.perspective} className="hint" style={{ marginTop: 6 }}>
          {a.term} · {a.perspective}: “{a.comment}”
        </p>
      ))}
    </section>
  )
}
