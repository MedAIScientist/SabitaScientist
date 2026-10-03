# Gazzali

Research management platform for university labs: projects and Kanban boards,
experiments, publications, grants, IRB approvals, lab supervision (weekly
reports, meetings, join requests) and AI assistance (drafting, reviews,
copilot) on an OpenAI-compatible endpoint (Groq by default).

Production: https://medai.medipol.edu.tr

## Run locally

```bash
uv sync --dev
uv run python -m gazzali --host 0.0.0.0      # API + SPA on :7860, AI runner on :8001
```

Frontend development: `cd gazzali/frontend && npm ci && npm run dev`.

## Tests

```bash
uv run pytest
cd gazzali/frontend && npx vitest run
```

## Configuration

All settings are environment variables, read in `gazzali/settings.py`
(`GAZZALI_*`, `PM_*`, `GARAGE_*`, `OIDC_*`, `GROQ_API_KEY`, `PM_LLM_*`).
See `.env.example` and `CLAUDE.md`.

## Deploy

```bash
./deploy/deploy.sh medaiadm@medai-prod
```

Gazzali started as the project-management module of
[EvoScientist](https://github.com/EvoScientist/EvoScientist) (Apache-2.0) and
now runs independently of it.
