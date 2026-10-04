# Publication & AI Roadmap

**Scope decision:** this platform is for academic publication work. Course credits,
GPA and transcripts were removed; the registrar owns those. Everything below
serves one of two goals:

1. **A student publishes better** — a stronger manuscript, a submission that
   survives desk review, a revision that survives peer review.
2. **A student uses AI efficiently** — knowing what the AI costs, using it where it
   helps, and never letting it invent something a reviewer will catch.

Written after auditing the existing code, not from a generic checklist. Section 1
records what is already done; section 2 is what to build next, in order.

---

## 1. Where the system stands

Audited in `EvoScientist/pm/`:

| Capability | State |
|---|---|
| AI drafting (sections, whole paper, revision, reviewer response) | Exists — dispatched to the runner |
| Paper readiness gate (title, abstract, linked experiments, metrics, human revision, AI provenance) | Exists — `GET /supervision/papers/{id}/readiness` |
| Stage-aware tool suggestions | Exists — readiness returns `suggested_tools` |
| AI provenance per version (model + prompt hash) + disclosure statement | Exists |
| Citation verification against Semantic Scholar | Exists — `POST /projects/{id}/verify-citations`, **not** part of the gate |
| Ethics approvals (IRB) and grants, project-scoped | Exist — but nothing connected them to a paper |
| **Submission compliance statements** (guideline, data/code availability, COI, funding) | **Added** |
| **Ethics / funding cross-check in the gate** | **Added** |
| **AI usage accounting** (tokens per call, task, paper, person) | **Added** |
| References verified before submission | Missing |
| Reporting-guideline checklist (STROBE/CONSORT/PRISMA items) | Missing |
| Venue targeting (scope fit, deadlines, format limits, APC) | Missing |
| Reviewer comment → response tracking per point | Missing |
| Reproducibility bundle (claim → experiment → metric → run) | Partial (evidence endpoint only) |
| Token/cost budget alerts | Missing |

### Implemented in this pass

**Submission compliance (quality).** Five statements now live on the publication
(`reporting_guideline`, `data_availability`, `code_availability`,
`conflict_of_interest`, `funding_statement`), editable in the paper workspace, and
the readiness gate reads three of them as *required* — the checks a desk editor
applies before sending a paper out. The ethics and funding checks are
cross-checks, not duplicated fields: ethics is met only by an **approved** IRB
protocol on the paper's project, and funding is met by a typed statement *or* an
awarded/active grant on the project. Whitespace does not count as a declaration.

**AI usage accounting (efficiency).** Every LLM call now records what it consumed
into `ai_usage`: task label, model, prompt/completion tokens, latency, and
attribution to user, project and publication. Two writers feed it — the direct
path (`pm/_ai.py`) and the agent runner, which previously asked Groq to stream
*without* `include_usage`, i.e. it measured tokens and threw them away. Exposed at
`GET /ai/usage/summary` and `/records`, rendered as a panel on the home page and on
each paper.

Two honesty rules are built into that feature and should survive future edits:
provider-reported tokens and character-derived estimates are stored and displayed
separately and **never summed**; and there is **no cost figure**, because there is
no maintained price table and an invented number is worse than none.

### Two production bugs found while building this

Both were pre-existing, both were silent, and both were found by probing the live
system rather than by reading code.

1. **Every runner-backed AI feature was broken.** `pm_runner_model` defaulted to
   `mixtral-8x7b-32768`, which Groq has decommissioned — the API answers HTTP 400.
   The runner raised, emitted `status: failed`, and the drafting endpoint returned
   no text; the UI showed nothing happening. The default is now
   `openai/gpt-oss-120b` (verified working against the production key), with
   `PM_RUNNER_MODEL` as the deployment override. *Because Groq retires models on a
   schedule, this is a recurring failure class: pin a name in one place and give it
   a health check.*
2. **Asking Groq for token usage would have crashed the run.** With
   `stream_options: {"include_usage": true}`, the final chunk carries
   `"choices": []`. The runner indexed `chunk["choices"][0]` unconditionally, so the
   usage-only chunk raised `IndexError`, which the narrow
   `except json.JSONDecodeError` did not catch. The parsing is now a pure,
   tested function (`parse_stream_chunk`) that tolerates both shapes.

---

## 2. What to add next, in priority order

### P0 — Reference integrity (do this first)

The single highest-risk failure mode of AI-assisted writing is a fabricated or
misattributed reference. It is also the easiest to catch before a reviewer does.

- Persist verification results: a `citation_checks` table (publication_id,
  raw_reference, status, matched_doi, matched_title, matched_year, flags, checked_at).
- Extract references from the latest version's text (the parser already exists in
  `pm/s2/queries.py`) and verify each against the S2 database.
- Add a gate check: **"all references verified"** — required. Show unmatched and
  suspicious entries inline in the paper workspace.
- Add a retraction check. `flags` already exists in the verification result shape;
  wire a retracted-paper signal into it.
- Refuse to insert an unverified citation into a draft without an explicit override
  that is recorded in the version's provenance.

*Why first:* it protects the paper, it is fully local (no external API), and the
verification engine already exists — this is wiring, not research.

### P1 — Reporting-guideline checklist per study type

`reporting_guideline` currently proves only that the author *named* a guideline.
The next step is the actual items: STROBE for observational cohorts, CONSORT for
trials, PRISMA for reviews, TRIPOD for prediction models, STARD for diagnostics.
Each is a fixed list of items; many can be auto-checked against data already in the
system (sample size stated, ethics approval referenced, data availability stated,
limitations section present).

- Store the chosen guideline and per-item state on the publication (or a
  `publication_guideline_items` table).
- Auto-resolve the items that the system can see; leave the rest as a manual
  checklist with a note field.
- Surface unresolved items in the readiness gate, and export the checklist with the
  submission bundle.

*Why:* checklists are what distinguishes a desk-rejected manuscript from a reviewed
one, and reviewers are explicitly instructed to use them.

### P2 — Reviewer comment → response matrix

`publication_reviews` stores one free-text blob per round. Reviewers rarely accept a
blob as a response.

- New table `publication_review_comments`: review_id, publication_id, round,
  comment_text, category, severity, status (open / addressed / rebutted / wont_fix),
  response_text, resolved_at, resolved_by.
- Split a pasted review into individual points (the LLM can propose the split, the
  human confirms it).
- The existing `respond-to-reviewers` prompt should be fed the **unresolved** points
  only, with their responses, so the letter is grounded in what was actually said.
- Block "ready to resubmit" while any required point is open.

*Why:* the revision is where papers are won or lost, and this turns an unstructured
task into a checklist with a completion state.

### P3 — Venue targeting

- A venue record per publication: scope keywords, accepted article types, word and
  figure limits, reference style, submission deadline, APC, open-access policy.
- Match the manuscript against candidate venues (scope overlap from the abstract,
  deadline feasibility, past lab publications in that venue).
- Compare the manuscript against the venue's limits (word count per section, figure
  count, reference count) and flag overruns before submission.
- Track the submission decision timeline (submitted → first decision → revision →
  accept) so a student can see where time is actually lost.

*Why:* a correct-venue, within-limits submission avoids a large share of avoidable
desk rejections. The conference-deadline module already exists to build on.

### P4 — Reproducibility bundle

The system already links publications → experiments → metrics. Extend the chain to
the actual artefacts and export it.

- Claim-level links: statement/figure/table → metric → experiment → run ID →
  dataset/artefact.
- One-click export of a submission bundle: statements, checklist, verified
  references, figures with the code that produced them, and an environment record.
- Validate that every reported number in the abstract appears in a linked metric.

*Why:* "the number in the abstract cannot be traced to anything" is a common and
avoidable reviewer objection, and it is exactly what this platform is positioned to
solve.

### P5 — AI efficiency, once there is data

Usage accounting now collects the raw material. These come after a few weeks of it:

- **Budget alerts**: a per-student monthly token budget with a warning at 80%.
- **Task → model profiles**: route cheap tasks (formatting, checklist extraction,
  reference parsing) to a small model and reserve the large model for drafting.
  `suggested_tools` already knows the task, so the mapping has a natural home.
- **Cost, honestly**: a maintainable price table (model → input/output price per
  million tokens) kept in configuration, so cost is computed from real prices rather
  than hardcoded guesses. Until that exists, report tokens only.
- **Retrieval instead of stuffing**: build a bounded context pack per section from
  the student's own corpus (memory, previous drafts, linked experiments) rather than
  sending everything the project ever recorded. This is the largest token saving
  available and it also improves output quality.
- **Cache the shared prefix**: the system prompt plus paper context repeats across
  section drafts; provider prompt caching removes most of that cost.

### P6 — Smaller, cheap wins

- **A shadowed route.** `GET /api/v1/publications/{pub_id}/reviews` is declared in
  both `routes/publications.py` (typed, `response_model=list[ReviewResponse]`) and
  `routes/peer_review.py` (untyped dicts). `peer_review` is registered first and
  wins, so the typed handler is dead code and its response validation never runs.
  They also share a function name, which is why FastAPI reports a duplicate
  operation ID. Removing the duplicate restores validation; keeping both is how a
  field silently goes missing later.
- Section-level word counts against venue limits.
- A "what changed in this revision" diff between two versions.
- Export the AI disclosure statement in the format journals ask for.

---

## 3. Suggested sequence

| Order | Item | Payoff |
|---|---|---|
| 1 | P0 reference integrity | Prevents the worst AI failure mode |
| 2 | P1 reporting-guideline items | Converts a declaration into a real check |
| 3 | P2 reviewer comment matrix | Improves revision outcomes |
| 4 | P5 context packs + model routing | Largest AI cost reduction |
| 5 | P3 venue targeting | Fewer desk rejections |
| 6 | P4 reproducibility bundle | Stronger, more defensible papers |

## 4. How to tell it is working

Measurable from data the system already stores:

- Share of submissions whose readiness gate was at 100% **before** the submit action.
- Unverified references found per paper (should trend to zero before submission).
- Time from "reviewing" to "resubmitted" per round.
- Tokens per drafted section, and share of calls handled by the small model.
- Reviewer points resolved per round, and open points at resubmission (should be zero).
