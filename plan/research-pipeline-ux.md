# Research pipeline UX and integrity (AutoResearchClaw, paper arXiv:2605.20025)

Date: 2026-10-03. Builds on `plan/autoresearchclaw-integration.md` (runs, gates, registry
import, lab lessons are live). Branch per phase, tests per item, deploy after each phase.

## Facts this plan relies on (checked on a real NVIDIA run)

- Each ARC stage writes `stage-NN/stage_health.json` (`status`, `duration_sec`, `error`) and
  `stage-NN/decision.json` (`decision`: proceed/refine/pivot, `output_artifacts`, `next_stage`).
  Retried stages appear as extra `stage-NN*` folders.
- `stage-02/topic_evaluation.json`: `novelty`, `specificity`, `feasibility`, `overall` (0–10), `suggestion`.
- Debate panels write `perspectives/<role>.md` (stage 8: innovator, pragmatist, contrarian).
- `hitl/waiting.json`: `stage`, `stage_name`, `reason`, `since`, `context_summary`, `output_files`.
- Reject = Pivot in ARC (`decision: "pivot"`, reason taken from `message`).
- Profiles usable on CPU sandbox: `ml_tabular`, `medical_observational` (others force Docker).
- All AI drafts are stored through `crud.publications.create_version`.
- NVIDIA free key: ~40 requests/minute for everything; SMTP is not configured in prod
  (e-mail notifications become active when `EMAIL_SMTP_*` are set).

## Phase A — make the pipeline easy to follow and to start (step 1)

| # | Backend | Frontend | Check |
|---|---|---|---|
| A1 | Worker `GET /jobs/{id}/stages`: per stage `{stage, status, duration_sec, decision, error, artifacts, attempts}` + `topic_evaluation`. PM `GET /research-runs/{id}/stages` (visibility-checked). | — | worker + API tests on a fixture run dir |
| A2 | — | `stageCatalog.ts`: 23 stages → plain title, one-line explanation, phase. `RunTimeline`: 3 coloured phases, state + time per stage, click → artifacts list + viewer, Refine/Pivot/failed markers (the self-healing "decision tree"). | component test |
| A3 | Background sync thread started by `python -m gazzali` (not by tests): every 30 s refresh active runs, dispatch the queue, notify deciders once per gate (`research_runs.notified_stage`; e-mail via `notifications.py`). | NavBar badge with the number of gates waiting for me. | unit test of `sync_once()` |
| A4 | Queue: status `queued` (schema rebuild migration for the CHECK), `ARC_MAX_CONCURRENT` (default 1) counts only `running`. Start → queued when full; dispatch oldest first. `queue_position` in run JSON. | "Queued — position 2" chip. | tests: second run queues, dispatch after first ends |
| A5 | `GET /research-runs/usage`: PM LLM requests in the last 60 s (from `ai_usage`), limit 40, running/queued ARC runs. | Usage meter on the start form and the health page. | API test |
| A6 | `POST /research-runs/topic-check` (LLM rubric = ARC's topic evaluation, JSON). `GET /projects/{id}/research-datasets`: lab datasets in approved states with this project's IRBs. Worker/runs accept `domain` → ARC `--profile` (`ml_tabular`, `medical_observational`) or topic guidance (imaging, statistics). | 3-step wizard: Question (+ score and suggestion, template) → Data (picker, IRB auto-filled) → Review (mode, who approves what, queue position, usage). | API tests + component test |
| A7 | — | Gate card: plain stage title + explanation, inline preview of the stage's first artifact, quick-reply chips per stage group. | component test |

## Phase B — keep results honest (step 2, paper §3.4)

| # | Backend | Frontend | Check |
|---|---|---|---|
| B1 | `verify_numbers.py`: extract numbers from a draft, match against the publication's recorded metrics (linked experiments, else the project's), ±1 % like ARC. `create_version` runs it for AI drafts: unmatched → `[UNVERIFIED: x]`, summary stored in new column `publication_versions.verification_json`. Years, citations, small integers and section numbers are ignored. | Version list shows "n numbers verified / m unverified". | unit tests (match, tolerance, %, ignores) + integration on draft-section save |
| B2 | `citations.py`: parse references (DOI, arXiv id, title); check CrossRef → OpenAlex → arXiv → Semantic Scholar; title similarity → Verified / Suspicious / Hallucinated. `POST /publications/{id}/references/verify` on the latest version (or posted text). | References panel with the three labels and links. | tests with mocked HTTP |
| B3 | Worker `GET /jobs/{id}/deliverables` (manifest + paper file). PM `POST /research-runs/{id}/publication`: creates a publication (project, linked experiment) + version (`generated_by="autoresearchclaw"`, model), runs B1 on it. | "Create publication from this run" on finished runs. | API test with fake worker |

## Phase C — learning across runs and evaluation (step 3, paper §3.2, §3.5, §3.6, §4)

| # | Backend | Frontend | Check |
|---|---|---|---|
| C1 | `_ai.debate()`: K=3 role prompts in parallel + synthesizer. `generate-hypothesis` uses Innovator/Pragmatist/Contrarian; AI review uses Optimist/Skeptic/Methodologist. Output keeps the role sections + synthesis. | Existing pages show the structured result. | tests with fake LLM |
| C2 | `research_lessons.pinned`; pinned lessons always seeded first; `PATCH` pin/unpin. | Lab "Research memory" page: lessons by recency weight, pin/delete (PI). | API + component test |
| C3 | Import stores `primary_metric`, `primary_metric_std`, `metric_direction`, `conditions_json` on the run. | Compare table in the AutoResearchClaw tab (runs × primary metric ± std, best marked). | test |
| C4 | `GET /research-runs/evaluation` (lab PI: own labs; admin: all): per run completion, stages done, refines/pivots, interventions (audit log), unverified numbers, PI quality score (optional 1–10 at the final quality gate, `research_runs.pi_quality`). Approval stats per stage (SmartPause-lite): approve rate and a plain recommendation; no automatic skipping. | Evaluation page (for PIs). | API tests |

## Deploy

After each phase: full tests (`uv run pytest`, `npx vitest run`, build), DB backup, `deploy.sh`.
After phase A also build and start the `researchclaw` worker (token in server `.env`) and do
one real CoPilot run end to end on a small public dataset.

## Out of scope

Automatic gate skipping (needs approval history first), GPU, Docker-mode ARC profiles.
