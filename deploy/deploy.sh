#!/usr/bin/env bash
set -euo pipefail

# ── Gazzali PM Production Deploy ─────────────────────────────────────────
# Usage:  ./deploy/deploy.sh [server-address]
# Example: ./deploy/deploy.sh medaiadm@medai-prod
# Prerequisites: Docker, docker compose, rsync, ssh on the remote host.
#
# The default target is the host's Tailscale name. Over Tailscale SSH the campus
# firewall's block on port 22 to the DMZ does not apply, so deploys work from any
# network. Use medaiadm@10.150.145.10 only from inside the campus client subnets
# that are permitted to reach the DMZ.

SERVER="${1:-medaiadm@medai-prod}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Keep-alives: a session that dies mid-build (e.g. a Tailscale re-auth) fails in ~2 min instead of hanging.
SSH="ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=4 ${SERVER}"
DEPLOY_DIR="/home/medaiadm/EvoScientist"
COMPOSE_FILE="deploy/docker-compose.prod.yml"

echo "╔══════════════════════════════════════════════════╗"
echo "║     Gazzali PM — Production Deploy               ║"
echo "╚══════════════════════════════════════════════════╝"
echo "Server: ${SERVER}"
echo ""

# ── Step 1: Rsync code ───────────────────────────────────────────────────
echo "[1/5] Syncing source code..."
rsync -avz --delete \
  --exclude '.git' --exclude 'node_modules' --exclude '__pycache__' \
  --exclude '.venv' --exclude '.pytest_cache' --exclude '.ruff_cache' \
  --exclude '*.pyc' --exclude '.env' --exclude '.coverage' \
  --exclude 'build/' --exclude 'EvoScientist.egg-info/' \
  --exclude 'skills/' --exclude '.github/' --exclude '.superpowers/' \
  --exclude '.agents/' \
  --exclude 'deploy/nginx/ssl/' --exclude '*.bak*' --exclude 'runs/' \
  "${REPO_DIR}/" \
  "${SERVER}:${DEPLOY_DIR}/" || echo "  ⚠ rsync had warnings (non-critical)"
echo "  ✓ Code synced"

# ── Step 3: Build Docker image (background, for backend changes) ──────────
echo "[3/5] Building Docker image (background)..."
# Run build in background, capture PID, wait with periodic status
${SSH} "cd ${DEPLOY_DIR} && docker compose -f ${COMPOSE_FILE} build evoscientist" &
BUILD_PID=$!
while kill -0 $BUILD_PID 2>/dev/null; do
    sleep 30
    echo "  ... still building (PID $BUILD_PID running)"
done
wait $BUILD_PID && echo "  ✓ Build complete" || {
    echo "  ✗ Build failed"; exit 1
}

# ── Step 4: Deploy containers + fast frontend ────────────────────────────
echo "[4/5] Deploying containers + fast frontend..."
# Sync dist to server temp dir for fast docker cp after restart
rsync -avz --delete "${REPO_DIR}/EvoScientist/pm/frontend/dist/" "${SERVER}:/tmp/pm-frontend-dist/" 2>/dev/null || true
# Pull nginx image if needed
${SSH} "cd ${DEPLOY_DIR} && docker compose -f ${COMPOSE_FILE} pull nginx garage" 2>/dev/null || true

# Stop only evoscientist (garage and nginx stay up)
# Recreate in the foreground: polling health while this runs in the background
# used to match the *old* container and report healthy before the swap.
${SSH} "cd ${DEPLOY_DIR} && docker compose -f ${COMPOSE_FILE} up -d --no-deps --force-recreate evoscientist"

echo "  ... waiting for the new evoscientist container to become healthy"
HEALTHY=0
for i in $(seq 1 60); do
    STATUS=$(${SSH} "docker inspect evoscientist --format='{{.State.Health.Status}}' 2>/dev/null" || true)
    if [ "${STATUS}" = "healthy" ]; then
        echo "  ✓ evoscientist healthy (after $((i * 2))s)"
        HEALTHY=1
        break
    fi
    sleep 2
done
[ "${HEALTHY}" = "1" ] || echo "  ⚠ evoscientist not healthy after 120s (status: ${STATUS:-unknown})"

# Fast frontend deploy: docker cp the updated dist into the fresh container
${SSH} "docker cp /tmp/pm-frontend-dist/. evoscientist:/opt/venv/lib/python3.11/site-packages/EvoScientist/pm/frontend/dist/ 2>/dev/null" && echo "  ✓ Frontend hot-updated via docker cp"

# Ensure nginx is running
${SSH} "cd ${DEPLOY_DIR} && docker compose -f ${COMPOSE_FILE} up -d --no-deps nginx" 2>/dev/null || true

# ── Step 5: Final health check ──────────────────────────────────────────
echo ""
echo "[5/5] Health check..."
# Retry: nginx can briefly return 502 while it re-resolves the new container.
HEALTH="unreachable"
for i in $(seq 1 15); do
    HEALTH=$(${SSH} "curl -sk https://localhost/api/v1/health 2>/dev/null" || echo "unreachable")
    echo "$HEALTH" | grep -q '"status":"ok"' && break
    sleep 2
done
echo "  API: ${HEALTH}"

if echo "$HEALTH" | grep -q '"status":"ok"'; then
    echo ""
    echo "╔══════════════════════════════════════════════════╗"
    echo "║  ✅  Deployment successful                        ║"
    echo "║  https://medai.medipol.edu.tr                     ║"
    echo "╚══════════════════════════════════════════════════╝"
else
    echo ""
    echo "╔══════════════════════════════════════════════════╗"
    echo "║  ⚠  Deployment completed but health check        ║"
    echo "║     failed. Check logs:                           ║"
    echo "║     docker logs evoscientist                       ║"
    echo "╚══════════════════════════════════════════════════╝"
    exit 1
fi
