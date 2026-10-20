import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuth } from '../../auth'
import { LabDetail } from '../LabDetail'

vi.mock('react-router-dom', () => ({ useParams: () => ({ id: 'L1' }), useNavigate: () => vi.fn() }))
vi.mock('../../auth', () => ({ useAuth: vi.fn() }))
vi.mock('../../api', () => ({
  api: {
    getLab: vi.fn(), updateLab: vi.fn(), removeLabMember: vi.fn(), changeLabMemberRole: vi.fn(),
    addLabMember: vi.fn(), searchUsers: vi.fn(), listLabDatasets: vi.fn(), revokeDatasetGrant: vi.fn(), raiseDatasetStorage: vi.fn(),
  },
}))
import { api } from '../../api'
const mocked = vi.mocked(api)
const mockedAuth = vi.mocked(useAuth)

const member = (user_id: string, username: string, role: string) => ({ user_id, username, role, joined_at: '2026-10-01' })
const LAB = {
  id: 'L1', name: 'Bone Lab', pi_id: 'u-pi', department: '', university: '', created_at: '', updated_at: '',
  members: [member('u-pi', 'creator', 'pi'), member('u-real', 'real_pi', 'postdoc'), member('u-s', 'student1', 'ms')],
  member_count: 3, can_manage: true,
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}><LabDetail /></QueryClientProvider>)
}

function as(username: string, isAdmin = false) {
  mockedAuth.mockReturnValue({ username, isAdmin, role: isAdmin ? 'admin' : 'professor', token: 'tok', login: vi.fn(), logout: vi.fn() } as never)
}

beforeEach(() => {
  vi.resetAllMocks()
  mocked.getLab.mockResolvedValue(LAB as never)
  mocked.updateLab.mockResolvedValue(LAB as never)
  mocked.removeLabMember.mockResolvedValue(undefined as never)
  mocked.changeLabMemberRole.mockResolvedValue({} as never)
  mocked.listLabDatasets.mockResolvedValue([] as never)
  mocked.revokeDatasetGrant.mockResolvedValue(undefined as never)
})

describe('LabDetail — managing the roster', () => {
  test('a member role is changed from the roster', async () => {
    as('creator')
    renderPage()
    fireEvent.change(await screen.findByLabelText('Role of student1'), { target: { value: 'phd' } })
    await waitFor(() => expect(mocked.changeLabMemberRole).toHaveBeenCalledWith('L1', 'u-s', 'phd'))
  })

  test('removing a member asks first, and says what they lose', async () => {
    as('creator')
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Remove student1' }))
    expect(mocked.removeLabMember).not.toHaveBeenCalled()
    expect(screen.getByText(/lose this lab.s CVAT organisation and its datasets/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(mocked.removeLabMember).toHaveBeenCalledWith('L1', 'u-s'))
  })

  test("the PI's own row offers no role change or removal — the handover does that", async () => {
    as('creator')
    renderPage()
    await screen.findByLabelText('Role of student1')
    expect(screen.queryByLabelText('Role of creator')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Remove creator' })).not.toBeInTheDocument()
  })

  test('the PI hands the lab over and chooses what they become afterwards', async () => {
    as('creator')
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Hand this lab to another member/ }))
    fireEvent.change(screen.getByLabelText('New PI'), { target: { value: 'u-real' } })
    fireEvent.change(screen.getByLabelText('Former PI role'), { target: { value: 'postdoc' } })
    fireEvent.click(screen.getByRole('button', { name: 'Hand over' }))
    await waitFor(() => expect(mocked.updateLab).toHaveBeenCalledWith('L1', { pi_id: 'u-real' }))
    await waitFor(() => expect(mocked.changeLabMemberRole).toHaveBeenCalledWith('L1', 'u-pi', 'postdoc'))
    expect(mocked.updateLab.mock.invocationCallOrder[0]).toBeLessThan(mocked.changeLabMemberRole.mock.invocationCallOrder[0])
  })

  test('keeping the former PI as a co-PI makes no second call', async () => {
    as('creator')
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Hand this lab to another member/ }))
    fireEvent.change(screen.getByLabelText('New PI'), { target: { value: 'u-real' } })
    fireEvent.click(screen.getByRole('button', { name: 'Hand over' }))
    await waitFor(() => expect(mocked.updateLab).toHaveBeenCalled())
    expect(mocked.changeLabMemberRole).not.toHaveBeenCalled()
  })

  test('a co-manager who is not the PI cannot hand the lab over', async () => {
    as('real_pi')
    renderPage()
    await screen.findByLabelText('Role of student1')
    expect(screen.queryByRole('button', { name: /Hand this lab to another member/ })).not.toBeInTheDocument()
  })

  test('a refused change is shown, not swallowed', async () => {
    as('creator')
    mocked.changeLabMemberRole.mockRejectedValue(new Error("this is the lab's PI — hand the lab to another member first"))
    renderPage()
    fireEvent.change(await screen.findByLabelText('Role of student1'), { target: { value: 'phd' } })
    expect(await screen.findByRole('alert')).toHaveTextContent('hand the lab to another member first')
  })
})

describe('LabDetail — revoking a project\'s access to a dataset', () => {
  const grant = (over: Record<string, unknown> = {}) => ({
    id: 'g1', project_id: 'p1', project_name: 'Ankle study', admin_approved_at: '2026-10-12T09:00:00Z',
    granted_at: '2026-10-11T09:00:00Z', expires_at: null, revoked_at: null, active: true, cvat_project_id: null, ...over,
  })
  const dataset = (grants: unknown[], over: Record<string, unknown> = {}) => ({
    id: 'd'.repeat(32), name: 'DX ayak bilek 2019', modality: 'DX', status: 'sealed', retention_until: '2028-10-10', grants,
    estimated_bytes: null, ...over,
  })

  test('the PI sees which project reads each dataset, and revoking asks first and says what it does', async () => {
    as('creator')
    mocked.listLabDatasets.mockResolvedValue([dataset([grant()])] as never)
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: "Revoke Ankle study's access to DX ayak bilek 2019" }))
    expect(mocked.revokeDatasetGrant).not.toHaveBeenCalled()
    expect(screen.getByText(/lose read access within seconds — notebooks already running included/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Revoke' }))
    await waitFor(() => expect(mocked.revokeDatasetGrant).toHaveBeenCalledWith('d'.repeat(32), 'g1'))
  })

  test('an unapproved share is withdrawn, and says nobody has access through it yet', async () => {
    as('creator')
    mocked.listLabDatasets.mockResolvedValue([dataset([grant({ admin_approved_at: null, active: false })])] as never)
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /^Withdraw Ankle study/ }))
    expect(screen.getByText(/never approved, so nobody reads the dataset through it/)).toBeInTheDocument()
  })

  test('revoked shares are history, not a button', async () => {
    as('creator')
    mocked.listLabDatasets.mockResolvedValue([dataset([grant({ revoked_at: '2026-10-15T09:00:00Z', active: false })])] as never)
    renderPage()
    expect(await screen.findByText(/Revoked: Ankle study \(2026-10-15\)/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Revoke Ankle study/ })).not.toBeInTheDocument()
  })

  test('someone who cannot manage the lab is not shown the datasets panel', async () => {
    as('student1')
    mocked.getLab.mockResolvedValue({ ...LAB, can_manage: false } as never)
    renderPage()
    await screen.findByText('MEMBERS (3)')
    expect(mocked.listLabDatasets).not.toHaveBeenCalled()
  })
})

describe('LabDetail — storage reserved for a dataset', () => {
  const ds = (over: Record<string, unknown> = {}) => ({
    id: 'e'.repeat(32), name: 'CT thorax 2024', modality: 'CT', status: 'approved', retention_until: '2028-10-10',
    grants: [], estimated_bytes: 2 * 1024 ** 3, ...over,
  })

  test('a platform admin raises it while the delivery can still write', async () => {
    as('root', true)
    mocked.listLabDatasets.mockResolvedValue([ds()] as never)
    mocked.raiseDatasetStorage.mockResolvedValue({} as never)
    renderPage()
    expect(await screen.findByText('Storage: 2 GiB reserved')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Reserve more…' }))
    const field = screen.getByLabelText('New storage for CT thorax 2024 (GiB)')
    fireEvent.change(field, { target: { value: '1' } })
    expect(screen.getByRole('button', { name: 'Reserve' })).toBeDisabled()
    expect(screen.getByText('Storage can only be raised.')).toBeInTheDocument()
    fireEvent.change(field, { target: { value: '8' } })
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }))
    await waitFor(() => expect(mocked.raiseDatasetStorage).toHaveBeenCalledWith('e'.repeat(32), 8 * 1024 ** 3))
  })

  test('a lab PI sees the reservation but cannot change it', async () => {
    as('creator')
    mocked.listLabDatasets.mockResolvedValue([ds({ estimated_bytes: null })] as never)
    renderPage()
    expect(await screen.findByText('Storage: no limit set')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reserve more…' })).not.toBeInTheDocument()
  })

  test('a sealed dataset offers no raise — nothing writes to it any more', async () => {
    as('root', true)
    mocked.listLabDatasets.mockResolvedValue([ds({ status: 'sealed' })] as never)
    renderPage()
    await screen.findByText('Storage: 2 GiB reserved')
    expect(screen.queryByRole('button', { name: 'Reserve more…' })).not.toBeInTheDocument()
  })
})

describe('LabDetail — handover honesty and labs with no PI on record', () => {
  test('when only the second step fails, it says the lab WAS handed over', async () => {
    as('creator')
    mocked.changeLabMemberRole.mockRejectedValue(new Error('network down'))
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Hand this lab to another member/ }))
    fireEvent.change(screen.getByLabelText('New PI'), { target: { value: 'u-real' } })
    fireEvent.change(screen.getByLabelText('Former PI role'), { target: { value: 'postdoc' } })
    fireEvent.click(screen.getByRole('button', { name: 'Hand over' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('The lab was handed to real_pi, but creator keeps the PI role')
  })

  test("a legacy lab's PI-role members get no role dropdown or remove button", async () => {
    as('creator')
    mocked.getLab.mockResolvedValue({
      ...LAB, pi_id: null,
      members: [member('u-pi', 'creator', 'pi'), member('u-co', 'co_pi', 'pi'), member('u-s', 'student1', 'ms')],
    } as never)
    renderPage()
    await screen.findByLabelText('Role of student1')
    for (const name of ['creator', 'co_pi']) {
      expect(screen.queryByLabelText(`Role of ${name}`)).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: `Remove ${name}` })).not.toBeInTheDocument()
    }
    expect(screen.queryByRole('button', { name: /Hand this lab to another member/ })).not.toBeInTheDocument()
    expect(screen.getByText(/PI: not recorded/)).toBeInTheDocument()
  })
})

describe('LabDetail — no first limit while a delivery fills an unlimited bucket', () => {
  test('a delivering dataset with no limit offers no reservation, and says why', async () => {
    as('root', true)
    mocked.listLabDatasets.mockResolvedValue([{
      id: 'f'.repeat(32), name: 'MR knee', modality: 'MR', status: 'delivering', retention_until: '2028-10-10',
      grants: [], estimated_bytes: null,
    }] as never)
    renderPage()
    expect(await screen.findByText('Storage: no limit set')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reserve more…' })).not.toBeInTheDocument()
    expect(screen.getByText(/first limit can no longer be set safely/)).toBeInTheDocument()
  })
})

describe('LabDetail — no one-way PI promotions', () => {
  test("in a lab with no PI on record a student's role cannot be set to PI", async () => {
    as('creator')
    mocked.getLab.mockResolvedValue({
      ...LAB, pi_id: null,
      members: [member('u-pi', 'creator', 'pi'), member('u-s', 'student1', 'ms')],
    } as never)
    renderPage()
    const select = await screen.findByLabelText('Role of student1')
    expect([...(select as HTMLSelectElement).options].map(o => o.value)).not.toContain('pi')
  })

  test('with a PI on record, the PI may make a co-PI', async () => {
    as('creator')
    renderPage()
    const select = await screen.findByLabelText('Role of student1')
    expect([...(select as HTMLSelectElement).options].map(o => o.value)).toContain('pi')
  })
})

describe('LabDetail — revoking an annotation share', () => {
  test('says the images staged into the project and CVAT are not removed', async () => {
    as('creator')
    mocked.listLabDatasets.mockResolvedValue([{
      id: 'd'.repeat(32), name: 'DX ayak bilek 2019', modality: 'DX', status: 'sealed', retention_until: '2028-10-10',
      estimated_bytes: null,
      grants: [{ id: 'g1', project_id: 'p1', project_name: 'Ankle study', admin_approved_at: '2026-10-12T09:00:00Z',
        granted_at: '2026-10-11T09:00:00Z', expires_at: null, revoked_at: null, active: true, cvat_project_id: 42 }],
    }] as never)
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: "Revoke Ankle study's access to DX ayak bilek 2019" }))
    expect(screen.getByText(/revoking does not remove those copies/)).toBeInTheDocument()
  })
})

describe('LabDetail — a first limit says what it can and cannot promise', () => {
  test('setting a first limit explains the empty-bucket rule and how a stopped delivery resumes', async () => {
    as('root', true)
    mocked.listLabDatasets.mockResolvedValue([{
      id: 'a'.repeat(32), name: 'US liver', modality: 'US', status: 'approved', retention_until: '2028-10-10',
      grants: [], estimated_bytes: null,
    }] as never)
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Reserve more…' }))
    expect(screen.getByText(/accepted only while the bucket is empty/)).toBeInTheDocument()
    expect(screen.getByText(/delivering again resumes it/)).toBeInTheDocument()
  })
})
