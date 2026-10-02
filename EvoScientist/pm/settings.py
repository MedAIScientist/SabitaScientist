"""PM settings and paths, read from the environment.

The PM used to read these through EvoScientist's ``config.settings`` and
``paths`` modules. It now owns them, so the PM runs without the rest of the
EvoScientist package. The environment variable names are unchanged, so
existing deployments (``.env`` / ``deploy/.env``) keep working.
"""

from __future__ import annotations

import os
from pathlib import Path


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key) or default


def _env_bool(key: str, default: bool) -> bool:
    value = os.environ.get(key)
    if not value:
        return default
    return value.strip().lower() not in ("0", "false", "no", "off")


def _env_path(key: str, default: Path) -> Path:
    value = os.environ.get(key)
    return Path(value).expanduser() if value else default


# Paths (same defaults as EvoScientist.paths had).
WORKSPACE_ROOT = _env_path("EVOSCIENTIST_WORKSPACE_DIR", Path.cwd())
RUNS_DIR = _env_path("EVOSCIENTIST_RUNS_DIR", WORKSPACE_ROOT / "runs")
DATA_DIR = _env_path("EVOSCIENTIST_DATA_DIR", Path.home() / ".evoscientist")
USER_SKILLS_DIR = _env_path("EVOSCIENTIST_SKILLS_DIR", WORKSPACE_ROOT / "skills")
GLOBAL_SKILLS_DIR = DATA_DIR / "skills"

# The model that answers the PM's direct AI calls and the copilot. It must emit
# native tool calls for the copilot (see DEFAULT_MODEL history in git).
DEFAULT_LLM_MODEL = "qwen/qwen3.6-27b"
DEFAULT_LLM_BASE_URL = "https://api.groq.com/openai/v1"


def get_llm_config() -> dict:
    """Any OpenAI-compatible endpoint; Groq by default."""
    return {
        "model": _env("PM_LLM_MODEL") or _env("EVOSCIENTIST_AUXILIARY_MODEL", DEFAULT_LLM_MODEL),
        "base_url": _env("PM_LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
        "api_key": _env("PM_LLM_API_KEY") or _env("GROQ_API_KEY"),
    }


def get_runner_model() -> str:
    """PM_RUNNER_MODEL, or "" to use the runner's default."""
    return _env("PM_RUNNER_MODEL")


def get_runner_url() -> str:
    """Return the PM agent-runner base URL."""
    return _env("PM_RUNNER_URL", "http://127.0.0.1:8001")


def get_cors_origins() -> list[str] | None:
    """Explicit CORS origins, or None for any origin."""
    raw = _env("PM_CORS_ORIGINS", "*")
    if raw == "*":
        return None
    return [o.strip() for o in raw.split(",") if o.strip()] or None


def docs_enabled() -> bool:
    return _env_bool("PM_DOCS_ENABLED", True)


def get_garage_config() -> dict:
    """Return S3/Garage storage config."""
    return {
        "endpoint": _env("GARAGE_S3_ENDPOINT", "http://localhost:3900"),
        "access_key": _env("GARAGE_ACCESS_KEY"),
        "secret_key": _env("GARAGE_SECRET_KEY"),
        "bucket": _env("GARAGE_BUCKET", "evoscientist"),
    }


def get_oidc_config() -> dict:
    """Return Microsoft 365 OIDC config."""
    return {
        "client_id": _env("OIDC_CLIENT_ID"),
        "client_secret": _env("OIDC_CLIENT_SECRET"),
        "tenant_id": _env("OIDC_TENANT_ID", "common"),
        "redirect_uri": _env("OIDC_REDIRECT_URI", "http://localhost:7860/api/v1/auth/oidc/callback"),
        "scope": _env("OIDC_SCOPE", "openid email profile"),
        "issuer_url": _env("OIDC_ISSUER_URL"),
    }


def get_smtp_config() -> dict:
    """Return SMTP config for notification e-mails."""
    return {
        "host": _env("EMAIL_SMTP_HOST"),
        "port": int(_env("EMAIL_SMTP_PORT", "587")),
        "user": _env("EMAIL_SMTP_USERNAME"),
        "password": _env("EMAIL_SMTP_PASSWORD"),
        "use_tls": _env_bool("EMAIL_SMTP_USE_TLS", True),
        "from_addr": _env("PM_SMTP_FROM", "noreply@evoscientist.local"),
        "base_url": _env("PM_BASE_URL", "http://localhost:7860"),
    }


def get_s2_db_path() -> str:
    """Return the Semantic Scholar citation DB path."""
    return _env("S2_DB_PATH")


def get_max_upload_bytes() -> int:
    """Return max attachment upload size in bytes."""
    return int(_env("PM_MAX_UPLOAD_MB", "50")) * 1024 * 1024
