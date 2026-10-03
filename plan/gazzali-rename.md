# EvoScientist → Gazzali full rename (user chose "everything, incl. infrastructure", 2026-10-03)

Branch: `feature/gazzali-rename` (from main 7414144). Nothing renamed yet.

## Code
- `git mv EvoScientist/pm gazzali`; delete the rest of `EvoScientist/` (unused core) and its root-level tests.
- Absolute imports `EvoScientist.pm.X` → `gazzali.X` (relative imports inside pm keep working).
- pyproject: name `gazzali`, only PM deps, script `gazzali = gazzali.__main__:main`.
- Env vars `EVOSCIENTIST_*` → `GAZZALI_*` (DATA_DIR, PM_DB, WORKSPACE_DIR, RUNS_DIR, SKILLS_DIR); drop AUXILIARY_MODEL (use PM_LLM_MODEL).
- Branding: NavBar label, e-mail subjects `[Gazzali]`, API title, default sender, `.config/evoscientist` pid path, docs/CLAUDE.md.
- Dockerfile: user `evosci` → `gazzali`, home `/home/gazzali/.gazzali`, image `gazzali:prod`.
- Compose: containers `gazzali`, `gazzali-garage`, `gazzali-nginx`; volumes `gazzali-data`, `gazzali-home`; nginx upstream `gazzali:7860`.
- Rebase `feature/autoresearchclaw` (2857432) on top afterwards.

## Server (medaiadm@medai-prod) — order matters
1. Backup `/data/pm.db` (sqlite backup API) and note old volume names:
   `deploy_evoscientist-prod-data` (/data), `deploy_evoscientist-home` (/home/evosci/.evoscientist, has skills/),
   `deploy_garage-prod-data` (keep, not renamed), stale `evoscientist_evoscientist-data` (unused?).
2. Copy volumes: `docker run --rm -v deploy_evoscientist-prod-data:/from -v deploy_gazzali-data:/to alpine cp -a /from/. /to/` (same for home; fix ownership for new uid if changed).
3. Garage bucket: `garage bucket alias <bucket-id> gazzali`; set `GARAGE_BUCKET=gazzali` (no copy).
4. Host scripts outside the repo (all use CONTAINER="evoscientist" and/or `EvoScientist.pm.*` modules):
   - /home/medaiadm/platform-desired-sync/run.sh (`python -m EvoScientist.pm.platform_sync`)
   - /home/medaiadm/platform-status-sync/run.sh (`python -m EvoScientist.pm.platform_pull`)
   - /home/medaiadm/cvat-org-reconciler/{watch.sh, run.sh, run-stats.sh, reconcile.py, cvat_stats_sync.py}
   Two `watch.sh` processes are running (one 45 days old); restart after the switch. Trigger mechanism for
   run.sh scripts not yet found (no user crontab / timers seen) — find it before switching.
5. Move deploy dir `/home/medaiadm/EvoScientist` → `/home/medaiadm/Gazzali` (nginx conf, ssl, garage.toml, .env live there); update `deploy/deploy.sh` DEPLOY_DIR.
6. Stop old containers (do NOT remove), start new ones; verify health, login, copilot, S3 attachment download.
7. Rollback: stop new, `docker start evoscientist evoscientist-garage evoscientist-nginx`.

Not renamed: GitHub repo and local checkout dir (outward-facing / user's choice).
