"""Bridge between PM module and the EvoScientist runtime infrastructure.

Centralizes access to EvoScientist's path resolution, configuration, and
environment so individual route/CRUD modules don't duplicate env-var reads,
hardcoded fallbacks, or workspace-logic forks.
"""

from __future__ import annotations

from pathlib import Path

from ..config.settings import get_effective_config
from ..paths import DATA_DIR, WORKSPACE_ROOT


def get_runner_url() -> str:
    """Return the PM agent-runner base URL from EvoScientistConfig."""
    return get_effective_config().pm_runner_url


def get_pm_db_path() -> Path:
    """Return the PM SQLite DB path under EvoScientist's DATA_DIR."""
    cfg = get_effective_config()
    if cfg.pm_db_path:
        p = Path(cfg.pm_db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / "projects.db"


def resolve_workspace_run_dir(workspace_dir: str | None = None) -> str:
    """Resolve a workspace run directory compatible with ``_run_agent`` patterns.

    Uses EvoScientist's ``WORKSPACE_ROOT`` / ``RUNS_DIR`` machinery instead of
    duplicated ``os.getenv("EVOSCIENTIST_WORKSPACE_DIR", ...)`` fallbacks.
    """
    base = Path(workspace_dir) if workspace_dir else WORKSPACE_ROOT
    runs = base / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    return str(runs)


def get_garage_config() -> dict:
    """Return S3/Garage storage config from EvoScientistConfig."""
    cfg = get_effective_config()
    return {
        "endpoint": cfg.pm_garage_s3_endpoint,
        "access_key": cfg.pm_garage_access_key,
        "secret_key": cfg.pm_garage_secret_key,
        "bucket": cfg.pm_garage_bucket,
    }


def get_oidc_config() -> dict:
    """Return OIDC config from EvoScientistConfig."""
    cfg = get_effective_config()
    return {
        "client_id": cfg.pm_oidc_client_id,
        "client_secret": cfg.pm_oidc_client_secret,
        "tenant_id": cfg.pm_oidc_tenant_id,
        "redirect_uri": cfg.pm_oidc_redirect_uri,
        "scope": cfg.pm_oidc_scope,
        "issuer_url": cfg.pm_oidc_issuer_url,
    }


def get_smtp_config() -> dict:
    """Return SMTP config from EvoScientistConfig (shared channel settings)."""
    cfg = get_effective_config()
    return {
        "host": cfg.email_smtp_host,
        "port": cfg.email_smtp_port,
        "user": cfg.email_smtp_username,
        "password": cfg.email_smtp_password,
        "use_tls": cfg.email_smtp_use_tls,
        "from_addr": cfg.pm_smtp_from,
        "base_url": cfg.pm_base_url,
    }


def get_s2_db_path() -> str:
    """Return the Semantic Scholar citation DB path from EvoScientistConfig."""
    return get_effective_config().pm_s2_db_path


def get_max_upload_bytes() -> int:
    """Return max attachment upload size in bytes from EvoScientistConfig."""
    return int(get_effective_config().pm_max_upload_mb or 50) * 1024 * 1024
