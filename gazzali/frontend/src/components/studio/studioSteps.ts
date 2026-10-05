// The Paper Studio pipeline in plain language, and which step comes next.
export interface Step { key: string; title: string; explain: string; action: string; done: string; ai?: boolean }

export const STEPS: Step[] = [
  { key: 'setup', title: 'Paper basics', explain: 'Give the paper a title and link it to its project, so the studio knows where your results are.',
    action: 'Open paper details', done: 'The paper has a title and a project.' },
  { key: 'evidence', title: 'Gather your results', explain: 'Save a fixed copy of what the paper may use: your experiments, measured numbers and references. Later changes to the project will not silently change the paper.',
    action: 'Save this evidence', done: 'Evidence saved. Save again whenever you add new results.' },
  { key: 'outline', title: 'Plan the key points', explain: 'AI proposes the main points of each section. Every point is linked to a piece of your evidence, so the paper never says something you cannot back up.',
    action: 'Suggest key points', done: 'Key points ready. Check them before writing.', ai: true },
  { key: 'sections', title: 'Write the sections', explain: 'Pick a section. Let AI write a first draft from its key points, then edit it in your own words.',
    action: 'Write with AI', done: 'Main sections have text. Keep revising in your own words.', ai: true },
  { key: 'coherence', title: 'Read it as a whole', explain: 'AI reads all sections together and points out contradictions, repetition and gaps between them.',
    action: 'Get feedback on the flow', done: 'Feedback received. Fix what you agree with.', ai: true },
  { key: 'integrity', title: 'Final check', explain: 'Before submitting: every number must come from your results, references must be real, and a person must have revised the text.',
    action: 'Run the final check', done: 'All checks passed.' },
  { key: 'submit', title: 'Prepare to submit', explain: 'Collect the manuscript, the point-to-evidence map, the saved evidence and the AI-use statement in one package.',
    action: 'Build the package', done: 'The paper is submitted.' },
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
    irb: 'Ethics approval', grants: 'Grant', data: 'Data source', ethics: 'Ethics approval', funding: 'Grant', literature: 'Reference' } as Record<string, string>)[kind] ?? kind.replace(/_/g, ' ')
  return n === 1 ? base : `${base}s`
}
