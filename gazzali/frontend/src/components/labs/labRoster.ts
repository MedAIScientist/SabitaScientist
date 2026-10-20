import type { Lab, LabMember_ } from '../../api'

/** The roles the API accepts for a lab member (schemas.py: pi|postdoc|phd|ms|visitor). */
export const LAB_ROLES = [
  { value: 'pi', label: 'PI' },
  { value: 'postdoc', label: 'Postdoc' },
  { value: 'phd', label: 'PhD' },
  { value: 'ms', label: 'MS' },
  { value: 'visitor', label: 'Visitor' },
] as const

/**
 * The member who is the lab's PI. `labs.pi_id` when set. A lab created before pi_id was recorded
 * has none: then its PI is its one 'pi'-role member — and nobody when several hold that role,
 * because the system cannot tell which of them leads the lab (the server refuses to let any of
 * them claim it; a platform admin decides).
 */
export function labPi(lab: Lab): LabMember_ | undefined {
  if (lab.pi_id) return lab.members.find(m => m.user_id === lab.pi_id)
  const pis = lab.members.filter(m => m.role === 'pi')
  return pis.length === 1 ? pis[0] : undefined
}

/** Whether the signed-in user is this lab's PI — who, besides a platform admin, may hand it over. */
export function isLabPi(lab: Lab, username: string | null): boolean {
  if (!username) return false
  const pi = labPi(lab)
  return !!pi && pi.username === username
}

/**
 * Whether this member's role can be changed or the member removed through the roster. The lab's
 * PI cannot (the server answers 409): the lab would be left with a PI without PI powers, or
 * none. Handing the lab over is the way; a platform admin may still act directly, for repairs.
 */
export function rosterLocked(lab: Lab, member: LabMember_, isAdmin: boolean): boolean {
  if (isAdmin) return false
  // With no PI on record, every 'pi'-role member is protected — the server's rule (409).
  return lab.pi_id ? member.user_id === lab.pi_id : member.role === 'pi'
}

/** Who the lab could be handed to: every other current member. */
export function handoverCandidates(lab: Lab): LabMember_[] {
  const pi = labPi(lab)
  return lab.members.filter(m => m.user_id !== pi?.user_id)
}

/**
 * The roles this user may give a member here. In a lab with no PI on record, only a platform admin
 * may make someone a PI: every PI-role member of such a lab is protected, so a non-admin's
 * promotion could never be undone (the server answers 409).
 */
export function assignableRoles(lab: Lab, isAdmin: boolean) {
  return LAB_ROLES.filter(r => r.value !== 'pi' || isAdmin || !!lab.pi_id)
}
