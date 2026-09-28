#!/usr/bin/env bash
set -euo pipefail

# ────────────────────────────────────────────────────────────────────────────
# Authentik IAM Setup — deploy alongside EvoScientist PM
# ────────────────────────────────────────────────────────────────────────────
# All generated secrets are written to the project root .env so docker compose
# can interpolate them (env_file values are NOT used for compose interpolation).
#
# Prerequisites:
#   1. Microsoft Entra ID App Registration with:
#      - Redirect URI: http://localhost:9000/source/oauth/callback/microsoft/
#        (for container-to-container: http://authentik-server:9000/...)
#      - ID tokens enabled
#   2. MICROSOFT_OAUTH_* vars in ../.env (already populated)
#
# Usage:
#   bash deploy/setup-authentik.sh          # generates secrets + starts stack
#
# Then:
#   1. Visit http://localhost:9000 and log in with admin credentials
#   2. Admin → Applications → EvoScientist PM → Provider tab
#   3. Copy Client ID / Client Secret into ../.env as OIDC_CLIENT_ID / OIDC_CLIENT_SECRET
#   4. docker compose restart evoscientist
# ────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Authentik IAM Setup ==="
echo ""

# ── 1. Generate secrets ─────────────────────────────────────────────────────
# Docker compose reads .env from the "project directory" (determined by the
# first -f file's location, or --project-directory). We write secrets to both
# deploy/.env and ../.env (project root) to cover both scenarios.

ROOT_ENV="../.env"
LOCAL_ENV=".env"

ensure_secret() {
    local var="$1"
    # Check root .env (preferred location for compose interpolation)
    local current
    current=$(grep -s "^${var}=" "$ROOT_ENV" | tail -1 | cut -d= -f2- || true)
    if [ -z "$current" ]; then
        local secret
        secret=$(openssl rand -hex 32)

        # Write to all env files that compose might read
        for f in "$ROOT_ENV" "$LOCAL_ENV"; do
            if grep -q "^${var}=" "$f" 2>/dev/null; then
                sed -i '' "s/^${var}=.*/${var}=${secret}/" "$f"
            else
                echo "" >> "$f"
                echo "${var}=${secret}" >> "$f"
            fi
        done
        echo "  ✓ Generated $var"
    else
        echo "  ✓ $var already set"
    fi
}

ensure_secret "AUTHENTIK_SECRET_KEY"
ensure_secret "AUTHENTIK_BOOTSTRAP_PASSWORD"
ensure_secret "AUTHENTIK_BOOTSTRAP_TOKEN"
# Generate SINGLE postgres password, write as both compose var + Authentik var
ensure_secret "AUTHENTIK_POSTGRES_PASSWORD"
# Generate PM OIDC credentials for Authentik provider
ensure_secret "OIDC_CLIENT_ID"
ensure_secret "OIDC_CLIENT_SECRET"
# Mirror to Authentik-specific name so server gets it via env_file at runtime
PG_VAL="$(grep -s '^AUTHENTIK_POSTGRES_PASSWORD=' "$ROOT_ENV" | tail -1 | cut -d= -f2- || true)"
if [ -n "$PG_VAL" ]; then
    for f in "$ROOT_ENV" "$LOCAL_ENV"; do
        if grep -q "^AUTHENTIK_POSTGRESQL__PASSWORD=" "$f" 2>/dev/null; then
            sed -i '' "s/^AUTHENTIK_POSTGRESQL__PASSWORD=.*/AUTHENTIK_POSTGRESQL__PASSWORD=${PG_VAL}/" "$f"
        else
            echo "AUTHENTIK_POSTGRESQL__PASSWORD=${PG_VAL}" >> "$f"
        fi
    done
fi

# Export for compose interpolation (compose reads shell env before .env file)
AUTHENTIK_POSTGRES_PASSWORD="$PG_VAL"
export AUTHENTIK_POSTGRES_PASSWORD

# ── 2. Check Microsoft OAuth credentials ────────────────────────────────────

echo ""
echo "Checking Microsoft OAuth credentials..."
MISSING_MS=0
for var in MICROSOFT_OAUTH_CLIENT_ID MICROSOFT_OAUTH_CLIENT_SECRET MICROSOFT_OAUTH_TENANT_ID; do
    val=$(grep -s "^${var}=" "$ROOT_ENV" | cut -d= -f2- || true)
    if [ -z "$val" ]; then
        echo "  ✗ $var is not set in .env"
        MISSING_MS=1
    else
        echo "  ✓ $var is set"
    fi
done

if [ "$MISSING_MS" -eq 1 ]; then
    echo ""
    echo "WARNING: Microsoft OAuth credentials are required for 'Sign in with Microsoft'."
    echo "Add these to .env:"
    echo "  MICROSOFT_OAUTH_CLIENT_ID=<Entra ID Application ID>"
    echo "  MICROSOFT_OAUTH_CLIENT_SECRET=<Entra ID Client Secret>"
    echo "  MICROSOFT_OAUTH_TENANT_ID=<Entra ID Tenant ID>"
fi

# ── 3. Start Authentik ──────────────────────────────────────────────────────
# --env-file explicitly points compose to the root .env for interpolation.
# env_file paths in the compose files are still resolved relative to the
# compose file's own directory (deploy/), NOT to --env-file.

echo ""
echo "Starting Authentik..."
cd ..
docker compose -f deploy/docker-compose.authentik.yml \
               --env-file .env up -d

echo ""
echo "=== Authentik is starting up ==="
echo ""
echo "  Admin UI:    http://localhost:9000"
echo "  PM Login:    http://localhost:7860/login"
echo ""
echo "OIDC credentials auto-generated — PM is already configured."
echo ""
echo "Next steps:"
echo "  1. Open http://localhost:9000 and log in:"
echo "     User:     admin@evoscientist.local"
echo "     Password: (check AUTHENTIK_BOOTSTRAP_PASSWORD in .env)"
echo ""
echo "  2. Verify Microsoft OAuth source:"
echo "     Admin → Sources → Microsoft — check consumer_key/secret"
echo ""
echo "  3. Open http://localhost:7860/login"
echo "     Click SIGN IN WITH MICROSOFT to test the flow"
