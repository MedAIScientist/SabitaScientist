// The 23 AutoResearchClaw stages in plain language (paper §3.1, Appendix A).
export type Phase = 'Discovery' | 'Experiment' | 'Writing'

export interface StageInfo { title: string; explain: string; phase: Phase; gate?: 'team' | 'pi' }

export const STAGES: Record<number, StageInfo> = {
  1: { title: 'Understanding the question', explain: 'Restates the goal and checks the computer it will run on.', phase: 'Discovery' },
  2: { title: 'Breaking the problem down', explain: 'Splits the question into parts and scores the topic.', phase: 'Discovery' },
  3: { title: 'Planning the literature search', explain: 'Chooses search terms and sources.', phase: 'Discovery' },
  4: { title: 'Collecting papers', explain: 'Searches OpenAlex, Semantic Scholar and arXiv.', phase: 'Discovery' },
  5: { title: 'Screening papers', explain: 'Keeps the papers that matter for the question.', phase: 'Discovery', gate: 'team' },
  6: { title: 'Reading the papers', explain: 'Turns each paper into a short knowledge card.', phase: 'Discovery' },
  7: { title: 'Finding the gap', explain: 'Summarises what is known and what is missing.', phase: 'Discovery' },
  8: { title: 'Debating hypotheses', explain: 'An innovator, a pragmatist and a contrarian argue; 2–4 testable hypotheses come out.', phase: 'Discovery' },
  9: { title: 'Designing the experiment', explain: 'Baselines, conditions, seeds and metrics.', phase: 'Discovery', gate: 'team' },
  10: { title: 'Writing the code', explain: 'Generates the experiment code and checks it before running.', phase: 'Experiment' },
  11: { title: 'Planning compute', explain: 'Fits the plan to the CPU and the time budget.', phase: 'Experiment' },
  12: { title: 'Running the experiments', explain: 'Runs in a sandbox with no network access.', phase: 'Experiment' },
  13: { title: 'Fixing and refining', explain: 'Repairs failures and improves weak results.', phase: 'Experiment' },
  14: { title: 'Analysing the results', explain: 'An optimist, a skeptic and a methodologist judge the evidence.', phase: 'Experiment', gate: 'pi' },
  15: { title: 'Deciding: proceed, refine or pivot', explain: 'Keeps going, improves, or returns to the hypotheses.', phase: 'Experiment' },
  16: { title: 'Outlining the paper', explain: 'Plans the sections and the story.', phase: 'Writing' },
  17: { title: 'Drafting the paper', explain: 'Writes the draft using only measured numbers.', phase: 'Writing' },
  18: { title: 'Simulated peer review', explain: 'Reviewers point out weaknesses.', phase: 'Writing' },
  19: { title: 'Revising the paper', explain: 'Addresses the review.', phase: 'Writing' },
  20: { title: 'Final quality check', explain: 'Checks claims, numbers and completeness.', phase: 'Writing', gate: 'pi' },
  21: { title: 'Saving what was learned', explain: 'Stores lessons for the lab’s next runs.', phase: 'Writing' },
  22: { title: 'Packaging the results', explain: 'Collects code, results and the paper.', phase: 'Writing' },
  23: { title: 'Verifying citations', explain: 'Removes references that do not exist.', phase: 'Writing' },
}

export const PHASES: { name: Phase; from: number; to: number; color: string }[] = [
  { name: 'Discovery', from: 1, to: 9, color: '#6366f1' },
  { name: 'Experiment', from: 10, to: 15, color: '#10b981' },
  { name: 'Writing', from: 16, to: 23, color: '#f59e0b' },
]

export function stageTitle(stage: number | null | undefined): string {
  return stage ? STAGES[stage]?.title ?? `Stage ${stage}` : 'Waiting to start'
}

/** One-click guidance for a gate, by where the run is. */
export function quickReplies(stage: number | null | undefined): string[] {
  if (!stage || stage <= 13) {
    return ['Reduce the number of conditions', 'Add a simple baseline', 'Use 5 seeds and report mean ± std', 'Add a statistical test']
  }
  if (stage <= 15) {
    return ['Report confidence intervals', 'Tone down claims the data does not support', 'Add an ablation']
  }
  return ['Shorten the abstract', 'Add a limitations section', 'Check every number against the results']
}

export function formatDuration(sec: number | null | undefined): string {
  if (sec == null) return ''
  if (sec < 60) return `${Math.round(sec)}s`
  const m = Math.floor(sec / 60)
  return m < 60 ? `${m}m ${Math.round(sec % 60)}s` : `${Math.floor(m / 60)}h ${m % 60}m`
}
