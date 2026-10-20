import { describe, expect, it } from 'vitest'
import type { Lab, Project } from '../../../api'
import { appendNote, approvalBlockers, canWriteFor, irbActions, isLapsed, parseDocuments, todayUtc } from '../irbModel'

const project = (over: Partial<Project> = {}): Project => ({
  id: 'p1', name: 'test-project', description: null, created_by: 'u1', created_at: '', archived_at: null,
  members: [{ user_id: 'u1', username: 'pi1', role: 'owner', added_at: '' }], lab_id: 'l1', ...over,
})
const lab = (role: string): Lab => ({
  id: 'l1', name: 'test-lab', pi_id: 'u9', department: '', university: '', created_at: '', updated_at: '',
  members: [{ user_id: 'u2', username: 'student1', role, joined_at: '' }], can_manage: false,
} as unknown as Lab)

describe('irbActions — only offer what the server allows', () => {
  const writer = { isAdmin: false, canWrite: true }
  const admin = { isAdmin: true, canWrite: true }
  const outsider = { isAdmin: false, canWrite: false }

  it('a draft can be submitted or closed by a writer, never decided', () => {
    expect(irbActions({ status: 'draft' }, writer)).toEqual(['submit', 'close'])
    expect(irbActions({ status: 'draft' }, admin)).not.toContain('approve')
  })

  it('only a platform admin decides a submitted record; a writer may withdraw it', () => {
    expect(irbActions({ status: 'submitted' }, writer)).toEqual(['withdraw'])
    expect(irbActions({ status: 'submitted' }, admin)).toEqual(['withdraw', 'approve', 'reject'])
  })

  it('an approved record is sealed: only an admin may end it', () => {
    expect(irbActions({ status: 'approved' }, writer)).toEqual([])
    expect(irbActions({ status: 'approved' }, admin)).toEqual(['expire', 'close'])
  })

  it('someone who cannot write gets nothing, and closed is terminal', () => {
    expect(irbActions({ status: 'draft' }, outsider)).toEqual([])
    expect(irbActions({ status: 'closed' }, admin)).toEqual([])
  })
})

describe('approvalBlockers mirrors irb.py', () => {
  const today = '2026-10-16'
  it('needs a decision date, a validity after today, and a document', () => {
    expect(approvalBlockers({ approval_date: '', expiry_date: '', documents: [] }, today)).toHaveLength(3)
  })
  it('an expiry of today is already too late (the server compares <=)', () => {
    expect(approvalBlockers({ approval_date: '2026-10-01', expiry_date: today, documents: ['x'] }, today))
      .toEqual(['The approval must still be valid after today.'])
  })
  it('complete evidence is sendable', () => {
    expect(approvalBlockers({ approval_date: '2026-10-01', expiry_date: '2027-10-01', documents: ['EK-2026/14'] }, today)).toEqual([])
  })
})

describe('helpers', () => {
  it('document references are one per line, blanks dropped', () => {
    expect(parseDocuments(' EK-1 \n\n EBYS 123 \n')).toEqual(['EK-1', 'EBYS 123'])
  })
  it('a rejection reason is appended, never replacing earlier notes', () => {
    expect(appendNote(null, 'Rejected: x')).toBe('Rejected: x')
    expect(appendNote('kept', 'Rejected: x')).toBe('kept\n\nRejected: x')
  })
  it('an approved record past its validity is lapsed; other states are not', () => {
    expect(isLapsed({ status: 'approved', expiry_date: '2026-10-16' }, '2026-10-16')).toBe(true)
    expect(isLapsed({ status: 'approved', expiry_date: '2026-10-17' }, '2026-10-16')).toBe(false)
    expect(isLapsed({ status: 'submitted', expiry_date: '2020-01-01' }, '2026-10-16')).toBe(false)
  })
  it('today is the UTC date, the clock the server uses', () => {
    expect(todayUtc(new Date('2026-10-16T23:30:00-03:00'))).toBe('2026-10-17')
  })
})

describe('canWriteFor mirrors _may_write_irb', () => {
  const who = (username: string, isAdmin = false) => ({ username, isAdmin })
  it('project owner or editor may write; a viewer may not', () => {
    expect(canWriteFor('p1', who('pi1'), [project()], [])).toBe(true)
    const viewer = project({ members: [{ user_id: 'u2', username: 'student1', role: 'viewer', added_at: '' }] })
    expect(canWriteFor('p1', who('student1'), [viewer], [lab('ms')])).toBe(false)
  })
  it("the pi/admin of the project's lab may write", () => {
    const viewer = project({ members: [{ user_id: 'u2', username: 'student1', role: 'viewer', added_at: '' }] })
    expect(canWriteFor('p1', who('student1'), [viewer], [lab('pi')])).toBe(true)
  })
  it('a platform admin may always write; an unknown project gives nobody else rights', () => {
    expect(canWriteFor('zzz', who('root', true), [], [])).toBe(true)
    expect(canWriteFor('zzz', who('pi1'), [project()], [])).toBe(false)
  })
})
