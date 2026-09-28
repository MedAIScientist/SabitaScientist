# Data-to-Paper Roadmap

Goal: a professor creates a project from a template, runs experiments, and gets a
submittable manuscript whose every number is traceable to recorded data.

Status key: ✅ done · 🔴 blocking · 🟡 important · 🟢 later

---

## ✅ Phase 0 — Structured results (done)

`experiment_metrics` table, CSV/TSV auto-parse on attachment upload, manual
metric entry, and a grounding rule injected into every drafting prompt. Result
entries are no longer truncated in AI context. 12 tests in
`tests/pm/test_experiment_metrics.py`.

Deliberately deferred from this phase:

- Metrics are per-experiment. Cross-experiment comparison tables (baseline vs
  proposed) are assembled by the model from separate tables. Add a comparison
  view only if professors ask — YAGNI until then.
- No units ontology, no metric-name normalization. `acc` and `accuracy` are two
  metrics. Fine until someone complains.

---

## 🔴 Phase 1 — Figures that plot real data

**Problem.** `POST /projects/{id}/experiments/{id}/generate-figures` asks the LLM
for "publication-quality figures" and stores its prose reply as a result entry.
It now receives the metrics table, so it will no longer invent values — but it
still cannot draw. The output is a description of a figure, not a figure.

**Fix.** Have the model emit matplotlib code that reads the source CSV, then
execute it and store the PNG as an attachment.

- Prompt returns a single fenced ```python block; nothing else.
- Execute in the existing sandbox/compute backend (`pm/compute/`) — never
  `exec()` in the API process.
- Script gets read-only access to the attachment's CSV and one output path.
- On failure, store the traceback in the entry. A broken figure is information;
  a hallucinated one is not.

**Files.** `pm/api/routes/ai_tools.py`, `pm/compute/`, new `pm/figures.py`.
**Effort:** medium — the sandbox call is the only real work.
**Verify.** Upload CSV → generate → PNG attachment exists with valid PNG bytes.

---

## ✅ Phase 2 — Drafts that survive (done)

Correction to the original diagnosis: the `text[:800]` truncation was already
fixed in commit `e903a0a`. The actual defect was that draft text went only to a
file under `RUNS_DIR` with just `file_path` in the DB, and **no endpoint ever
read that file back** — so an author could not retrieve their own draft. A
`restore` also copied only the note, restoring nothing.

Shipped: `content` + `section` columns on `publication_versions`; all four
drafting paths persist full text; `GET /publications/{id}/versions/{version_id}`
returns it; listing reports `content_length` but omits content so the payload
stays bounded; restore now copies text forward; the UI has an expandable draft
viewer.

Deferred: **version diffing** — the UI shows versions but not a diff between
them. Add when someone asks for it.

Also deferred: `draft-section` still creates an "in progress" placeholder
version at request time plus a real one on completion, so version numbers
advance by two per draft. Left alone because the frontend uses the placeholder
as its progress signal.

---

## 🔴 Phase 3 — Export (the last mile)

**Problem.** No LaTeX, DOCX, or PDF anywhere in `pm/`. The deliverable of a
paper tool is currently a markdown blob in SQLite.

**Fix.** One `subprocess.run(["pandoc", ...])` behind
`GET /publications/{id}/export?format=docx|pdf`.

- Assemble ordered sections from `publication_versions` (needs Phase 2 first).
- Bibliography comes from the existing bibtex export; pass `--citeproc`.
- Add pandoc to the Dockerfile.
- Per-venue `.tex` templates only when a professor names a venue — not upfront.

**Files.** new `pm/export_paper.py`, `pm/api/routes/publications.py`,
`Dockerfile`. **Effort:** low. **Depends on:** Phase 2.

---

## 🟡 Phase 4 — Citation verification in the loop

**Problem.** `/verify-citations`, the S2 DB, and bibtex parsing all exist, but
nothing forces a generated Introduction through them. An LLM writing related
work invents references, and the grounding rule only constrains numbers.

**Fix.** After any draft completes, extract citation-like strings, run the
existing verification, store per-reference status. UI flags unverified refs on
the publication page. Do not block the draft — flag it.

**Files.** `pm/api/routes/drafting.py`, `pm/s2/`, `pm/crud/publications.py`,
`PublicationDetail.tsx`. **Effort:** medium.

---

## 🟡 Phase 5 — Reproducibility linkage

**Problem.** `experiments` has no commit SHA, seed, environment, or link to
`runs`, despite the repo owning a runner and compute backends. A generated
Methods section cannot be reproducible.

**Fix.** Add `commit_sha`, `seed`, `env_notes`, `run_id` to `experiments` (4
migrations); surface them in the experiment form; inject into the Methods
prompt. When a compute job produces the results, populate them automatically.

**Files.** `pm/db.py`, `pm/models.py`, `pm/api/schemas.py`,
`pm/api/routes/experiments.py`, `ExperimentDetail.tsx`,
`pm/api/routes/drafting_helpers.py`. **Effort:** low-medium.

---

## ✅ Phase 6 — AI provenance and disclosure (done)

Shipped alongside Phase 2: `generated_by`, `model`, `prompt_hash` on
`publication_versions`, and `GET /publications/{id}/ai-disclosure` which builds
the statement from recorded history only. With no AI versions it says so rather
than emitting boilerplate; when the producing model is unknown (runner-generated
text) it says "an unrecorded language model" instead of naming one. The UI shows
the statement and an AI badge per version.

`prompt_hash` is a 16-char sha256 prefix, not the prompt — prompts embed patient
and project data that a provenance record should not duplicate.

Open gap: the **runner does not report which model it used**, so `model` is NULL
for agent-generated text. Fix by having `pm/runner/` return the model name in its
SSE completion event; then the disclosure can name it.

---

## 🟡 Phase 7 — Templates that carry domain rules

**Problem.** The three template YAMLs are phases + fill-in-the-blank protocols.
`medical.yaml` covers clinical trials but has no CONSORT/STROBE checklist and no
required-metrics list — exactly what gets a clinical paper desk-rejected.

**Fix.** Extend the template schema:

```yaml
reporting_checklist: CONSORT-2010     # or STROBE, ARRIVE, PRISMA, none
required_metrics:                     # drafting warns when unrecorded
  - name: primary_endpoint
  - name: p_value
```

Feed both into the Methods/Results prompts and show unmet requirements on the
publication page.

**Files.** `pm/templates/*.yaml`, `pm/api/routes/templates.py`,
`pm/api/routes/drafting_helpers.py`. **Effort:** low.
**Highest value per line in the roadmap.**

---

## 🟢 Phase 8 — Operational hardening

Not user-visible, but these bite at department scale:

- **Long LLM jobs run on FastAPI `BackgroundTasks`** — lost on restart, no
  retry, no visibility. The `runs` table already exists for this; move drafting
  jobs onto it.
- **SQLite concurrency** — enable WAL (`PRAGMA journal_mode=WAL`) before more
  than a handful of professors write concurrently. One line in `db.py`.
- **`schemas.py` is 1019 lines** — split per domain when it next needs editing,
  not before.
- **Test isolation** — several test modules permanently overwrite `get_db_path`
  on shared modules, so results depend on file ordering. Convert to
  `monkeypatch.setattr`.

---

## Suggested order

Phase 2 + 6 together (one migration), then 3, then 7, then 1, then 4, then 5.
Phase 8 is opportunistic except WAL, which is one line and should go in whenever
`db.py` is next touched.
