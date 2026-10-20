import { describe, expect, it } from 'vitest'
import type { Lab } from '../../../api'
import { assignableRoles, handoverCandidates, isLabPi, labPi, rosterLocked } from '../labRoster'

const member = (user_id: string, username: string, role: string) => ({ user_id, username, role, joined_at: '2026-10-01' })
const lab = (over: Partial<Lab> = {}): Lab => ({
  id: 'L1', name: 'Bone Lab', pi_id: 'u-pi', department: '', university: '', created_at: '', updated_at: '',
  members: [member('u-pi', 'creator', 'pi'), member('u-real', 'real_pi', 'postdoc'), member('u-s', 'student1', 'ms')],
  member_count: 3, can_manage: true, ...over,
})

describe('labRoster', () => {
  it('the PI is the pi_id holder, not whoever lists first with the pi role', () => {
    const l = lab({ members: [member('u-co', 'co_pi', 'pi'), member('u-pi', 'creator', 'pi')] })
    expect(labPi(l)?.username).toBe('creator')
  })

  it('a legacy lab without pi_id counts its pi-role member, as the server does', () => {
    expect(labPi(lab({ pi_id: null }))?.username).toBe('creator')
  })

  it('only the PI (or an admin, elsewhere) may hand over', () => {
    expect(isLabPi(lab(), 'creator')).toBe(true)
    expect(isLabPi(lab(), 'real_pi')).toBe(false)
    expect(isLabPi(lab(), null)).toBe(false)
  })

  it('the PI row is locked for everyone but a platform admin', () => {
    const l = lab()
    expect(rosterLocked(l, l.members[0], false)).toBe(true)
    expect(rosterLocked(l, l.members[0], true)).toBe(false)
    expect(rosterLocked(l, l.members[1], false)).toBe(false)
  })

  it('the lab can be handed to anyone but its current PI', () => {
    expect(handoverCandidates(lab()).map(m => m.username)).toEqual(['real_pi', 'student1'])
  })
})

describe('labRoster — a lab with no PI on record', () => {
  const legacy = (members = [member('u-a', 'kaplan', 'pi'), member('u-b', 'co_pi', 'pi'), member('u-s', 'student1', 'ms')]) =>
    lab({ pi_id: null, members })

  it('several PI-role members: nobody is the PI, so nobody may hand it over', () => {
    expect(labPi(legacy())).toBeUndefined()
    expect(isLabPi(legacy(), 'kaplan')).toBe(false)
    expect(isLabPi(legacy(), 'co_pi')).toBe(false)
  })

  it('every PI-role member is locked for a non-admin — one could otherwise remove the other', () => {
    const l = legacy()
    expect(rosterLocked(l, l.members[0], false)).toBe(true)
    expect(rosterLocked(l, l.members[1], false)).toBe(true)
    expect(rosterLocked(l, l.members[2], false)).toBe(false)
    expect(rosterLocked(l, l.members[0], true)).toBe(false)
  })

  it('a sole PI-role member is that lab\'s PI, and is locked too (no self-demotion)', () => {
    const l = legacy([member('u-a', 'kaplan', 'pi'), member('u-s', 'student1', 'ms')])
    expect(labPi(l)?.username).toBe('kaplan')
    expect(rosterLocked(l, l.members[0], false)).toBe(true)
  })
})

describe('assignableRoles', () => {
  const values = (l: Lab, admin: boolean) => assignableRoles(l, admin).map(r => r.value)
  it('a lab with a recorded PI may be given another PI', () => {
    expect(values(lab(), false)).toContain('pi')
  })
  it('a lab with no PI on record gets no new PI from a non-admin — a promotion there could not be undone', () => {
    expect(values(lab({ pi_id: null }), false)).not.toContain('pi')
    expect(values(lab({ pi_id: null }), true)).toContain('pi')
  })
})
