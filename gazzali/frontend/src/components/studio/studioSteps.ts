// The Paper Studio pipeline in plain language, and which step comes next.
export interface Step { key: string; title: string; explain: string; action: string }

export const STEPS: Step[] = [
  { key: 'setup', title: 'Set up', explain: 'Link the paper to its project so the studio can find its evidence.', action: 'Open paper details' },
  { key: 'evidence', title: 'Collect evidence', explain: 'Freeze what the paper may cite: experiments, measured results, references.', action: 'Freeze the evidence' },
  { key: 'outline', title: 'Outline & claims', explain: 'Each claim in the outline is tied to evidence, so nothing is said without support.', action: 'Generate the outline' },
  { key: 'sections', title: 'Draft sections', explain: 'Draft each section with AI, then revise it yourself.', action: 'Draft this section' },
  { key: 'coherence', title: 'Coherence', explain: 'Check that the sections tell one consistent story.', action: 'Run the coherence pass' },
  { key: 'integrity', title: 'Integrity check', explain: 'Blocks submission while numbers are unverified or no human has revised the text.', action: 'Run the integrity check' },
  { key: 'submit', title: 'Submission pack', explain: 'Manuscript, claim map, evidence snapshot and AI disclosure in one place.', action: 'Build the submission pack' },
]

export function nextStep(flags: Record<string, boolean>): Step | null {
  return STEPS.find(s => !flags[s.key]) ?? null
}

export function progress(flags: Record<string, boolean>): { done: number; total: number } {
  return { done: STEPS.filter(s => flags[s.key]).length, total: STEPS.length }
}

/** "task" → "Tasks"; labels for the evidence kinds the context returns. */
export function kindLabel(kind: string, n: number): string {
  const base = ({ project: 'Project', tasks: 'Task', task: 'Task', weekly: 'Weekly update', experiments: 'Experiment',
    experiment: 'Experiment', metrics: 'Measured result', references: 'Reference', bibliography: 'Reference',
    irb: 'Ethics approval', grants: 'Grant' } as Record<string, string>)[kind] ?? kind.replace(/_/g, ' ')
  return n === 1 ? base : `${base}s`
}
