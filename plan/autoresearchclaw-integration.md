# Applying AutoResearchClaw (arXiv:2605.20025) to Gazzali PM

Paper: Liu, Qiu et al., *AutoResearchClaw: Self-Reinforcing Autonomous Research with
Human-AI Collaboration*, arXiv:2605.20025v2 (May 2026). Code: aiming-lab/AutoResearchClaw (MIT).

## 1. What the paper claims, and what we take from it

| Mechanism (paper §) | What it does | Where it lives in our system |
|---|---|---|
| Multi-agent debate (§3.2) | K=3 roles + synthesizer, twice: hypotheses (Innovator / Pragmatist / Contrarian) and results (Optimist / Skeptic / Methodologist) | Inside ARC runs; **also** in PM's own one-shot features (`generate-hypothesis`, AI review) |
| Self-healing execution (§3.3) | Failure = information. Repair loop, then **Proceed / Refine / Pivot**. Sandbox with 3-phase network policy; read-only metric harness | Inside ARC. PM records every decision and failure as experiment entries |
| Verifiable reporting (§3.4) | Numeric registry of every measured value. Drafts may only use registry numbers; unmatched numbers in Abstract/Results reject the draft. 4-layer citation check | ARC for its papers; **PM drafting endpoints adopt the same gate** (this is our "no fabricated data" rule as code) |
| Human-in-the-loop (§3.5) | 7 modes; CoPilot = 6 high-leverage decision points; SmartPause | **PM is the human side**: gates appear in PM's Approvals inbox for the student and the supervising PI |
| Cross-run evolution (§3.6) | Lessons with severity s and decay w = s·exp(−ln2·Δt/T½), T½ = 30 days, injected into prompts | ARC `evolution/lessons.jsonl`, mirrored into PM **per lab** (the lab is our sharing boundary) |

Findings that drive our defaults (paper's numbers, ML topics, GPT-5.3-codex backbone):

- **CoPilot beats both extremes.** Mean quality 7.27 and 87.5% accept, vs 4.03 / 25% Full-Auto and
  5.19 / 50% Step-by-Step (Table 3). Default mode: **CoPilot**. Full-Auto only for dry runs.
- **Pre-experiment HITL fixes feasibility; post-experiment HITL fixes claim discipline.** Both are
  needed (Pre-only 4.28, Post-only 5.08). This maps onto our roles: the student shapes the design and
  the PI signs off on result analysis and the final draft.
- **Ablations:** removing debate cost the most quality (5.62 → 4.25); removing self-healing cost the most
  completion (10/10 → 6/10) (Table 5). Don't trim these to save tokens.

These numbers are the paper's, not ours. Section 6 says how we measure our own.

## 2. Constraints of our setting

- **Hardware:** medai-prod has 8 CPU, 15 GB RAM, no GPU, 26 GB free disk, and also runs the PM.
  ARC experiments there must be CPU-only and resource-capped. GPU work needs `experiment.ssh_remote`
  to a GPU host. **Open question: which GPU machine, if any?**
- **LLM:** Groq (OpenAI-compatible) is what we have. The paper used GPT-5.3-codex. Expect lower
  quality with open models; measure, don't assume.
- **Data (KVKK):** experiments on patient/imaging data must not send rows to an external LLM.
  The ARC LLM sees code, logs and metrics, so runs on identifiable data need a review rule
  (IRB-approved projects only, data mounted read-only, no raw rows in prompts).
- **Multi-user:** ARC is single-user (CLI + local dashboard, no auth). PM owns users, labs and
  permissions; ARC is never exposed outside the Docker network.
- **Scope of "all experiments":** ARC runs *computational* experiments. Wet-lab and clinical
  experiments in PM stay manual records. The plan routes every computational experiment through ARC.

## 3. Architecture

```
Browser ── nginx ── gazzali (API + SPA, runner)
                         │  REST (internal network only)
                         ├── researchclaw  (ARC worker: CLI pipeline + job wrapper, CPU-capped)
                         │     /data/arc/runs/<run_id>/{hitl/, artifacts/, registry, logs}
                         │     /data/arc/evolution/<lab_id>/lessons.jsonl
                         └── gpt-researcher (literature reports, internal only)
```

- **ARC worker container** (`researchclaw`): ARC installed, plus a ~150-line job wrapper (FastAPI):
  `POST /jobs` (topic, config, mode) → spawns `researchclaw run` in its own run dir;
  `GET /jobs/{id}` (stage, status); `GET /jobs/{id}/waiting`; `POST /jobs/{id}/response`.
  The wrapper only reads and writes ARC's documented files (`hitl/waiting.json`,
  `hitl/response.json`, registry, `lessons.jsonl`). ARC itself is not patched.
- **Experiments sandbox:** ARC `experiment.mode: sandbox` (subprocess inside the worker container),
  so no Docker socket is mounted (that would be root on the host). Container caps: 4 CPU, 6 GB RAM.
  The paper's 3-phase network policy needs Docker mode; we get phase 2 ("no network during
  execution") by running the worker on a network with egress limited to the LLM endpoint and
  literature APIs. GPU: `experiment.ssh_remote` with `use_docker: true` on the GPU host, when we have one.
- **PM side:** new `research_runs` table plus a background poller that syncs stage/status and
  surfaces `waiting.json` as an approval item.

## 4. Mapping each mechanism into PM

### 4.1 Human-in-the-loop = PM's supervision model
- Each ARC run belongs to a PM project and experiment, and is started by a student (or PI).
- CoPilot's six decision points become **approval items** in PM:
  - Pre-experiment gates (literature screening, Idea Workshop, Baseline Navigator): **student** decides,
    PI notified.
  - Post-experiment gates (result analysis, paper draft, quality gate): **PI must approve** (lab-scoped,
    via `supervision_scope`).
- Actions mirror ARC's `HumanInput`: approve / reject / edit / guide / rollback / abort. The PM writes
  `response.json`; audit middleware logs who decided what.
- Timeouts: ARC's default is 24 h. Use the weekly-meeting page as the reminder channel; never auto-proceed.
- SmartPause: enable after we have ~20 runs of approval history (it learns from override rates).

### 4.2 Verifiable reporting = our "no fabricated data" rule, enforced
- **Import the registry:** after each run, write its verified values (per-condition mean, std, seeds)
  into `experiment_entries` as structured metrics, with run id and commit hash.
- **PM drafting gate:** `draft-paper`, `draft-section` (results/abstract) and `revise` get the registry
  as pre-built tables. A post-hoc verifier re-extracts every number:
  - unmatched number in Abstract/Results/Experiments → reject the draft;
  - unmatched number elsewhere → visible placeholder `[UNVERIFIED]`.
- **Citations:** extend `verify-citations` from S2-only to the paper's 4 layers (CrossRef DOI → OpenAlex
  title → arXiv id → S2) and the Verified / Suspicious / Hallucinated labels. Hallucinated ones are removed.

### 4.3 Debate in PM's own AI features
`generate-hypothesis` and `generate-ai-review` currently make one LLM call. Change them to:
3 role prompts in parallel, then 1 synthesizer call. On Groq that is 4 cheap calls instead of 1.
The output keeps the paper's structure: 2–4 falsifiable hypotheses with testability criteria and
required baselines; for reviews, supported vs unsupported claims.

### 4.4 Self-healing, made visible
Each Proceed / Refine / Pivot decision and each repaired failure becomes an experiment entry
(`entry_type = decision | failure`). The experiment page shows the run as a tree of attempts, so a
"failed" run still leaves evidence the student and PI can read.

### 4.5 Cross-run evolution, per lab
- One lesson store per lab, so lessons stay inside the supervision boundary.
- After each run, new lines in `lessons.jsonl` are mirrored into a `research_lessons` table
  (category, severity, mitigation, run, created_at).
- The weight w = s·exp(−ln2·Δt/30 d) ranks them. The top-k by category are injected into new ARC
  runs (ARC does this natively from its store) and into PM's own AI prompts for that lab.
- The PI can pin, edit or delete lessons (bad lessons are worse than none).

### 4.6 Literature (GPT Researcher)
ARC has its own literature stage (OpenAlex / S2 / arXiv). GPT Researcher serves PM's standalone
`literature-review` and `research-ideation` endpoints, and its report can be handed to ARC as the
starting context of a run.

## 5. Work packages (each with a check)

| # | Work | Check |
|---|---|---|
| 0 | GPT Researcher container (internal), wired to `literature-review` | A report from PM's endpoint lists real arXiv/PubMed sources |
| 1 | `researchclaw` worker image + job wrapper; config from env (Groq base_url, sandbox, caps) | `POST /jobs` with an ARC-Bench ML topic in Full-Auto completes, or fails with a recorded reason |
| 2 | `research_runs` table, CRUD, routes, poller; "Run with AutoResearchClaw" on the experiment page | Run status in PM follows the run dir; tests for scoping (other labs can't see it) |
| 3 | HITL gates → Approvals inbox, student/PI routing, `response.json` writer | A CoPilot run pauses, the PI approves in PM, the run continues; audit log has the decision |
| 4 | Registry import + PM drafting number gate | A draft containing a number not in the registry is rejected (unit test with a fixture registry) |
| 5 | 4-layer citation verification | Known-good DOI verified; invented reference marked Hallucinated |
| 6 | Debate for hypothesis + AI review | Output has 3 role sections + synthesis; tests mock the LLM |
| 7 | Per-lab lesson store + decay ranking | Unit test of w(l) at Δt = 0, 30, 60 days (1, 0.5, 0.25 × s) |
| 8 | GPU via `ssh_remote` (blocked on a GPU host) | One run executes on the GPU host |

Order: 0 → 1 → 2 → 3 is the minimum useful product (runs + human gates). 4 and 5 protect integrity
and should ship before anyone drafts a paper from ARC results. 6–8 after.

## 6. How we will know it works (our numbers, not the paper's)

Per run, PM stores: completion, number and type of interventions, Proceed/Refine/Pivot counts,
registry size, verifier rejections, hallucinated citations removed, wall time, LLM tokens/cost
(already tracked in `ai_usage`), and the PI's 1–10 quality score at the final gate.

First evaluation: 5 ARC-Bench ML topics × {CoPilot, Full-Auto} on our hardware and Groq. Report the
results as measured, including failures. No result is claimed before it is run.

## 7. Risks

- **Open-model quality:** the paper's gains were measured with GPT-5.3-codex. Groq models may fail more
  stages. Mitigation: `PM_LLM_*`-style switch for ARC's `llm.base_url` / `primary_model`.
- **Resource contention on prod** (PM + ARC on 15 GB): container caps, one concurrent ARC run at first.
- **Sandbox escape / data exfiltration:** no Docker socket; egress-limited network; read-only data mounts.
- **ARC moves fast** (v0.5, many features): pin a commit; integrate only through its files and CLI.
- **Lesson poisoning:** PI review of lessons; severity caps; per-lab isolation.

## 8. Decisions needed from you

1. GPU host for ARC experiments (host, user, GPUs), or CPU-only for now?
2. Which LLM for ARC: Groq `openai/gpt-oss-120b` (cheap, weaker) or a stronger paid model for runs?
3. Default HITL mode: CoPilot for everyone, or Gate-Only for students without a PI?
4. Data policy: may ARC run on IRB-approved patient data, or only on public/synthetic datasets at first?
