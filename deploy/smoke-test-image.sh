#!/usr/bin/env bash
set -euo pipefail

# ── Gazzali image smoke test ───────────────────────────────────────────
# Usage:  ./deploy/smoke-test-image.sh [server-address]
# Example: ./deploy/smoke-test-image.sh medaiadm@medai-prod
#
# Answers one question: does the built image, on its own, start and serve the app?
#
# The deploy path cannot answer that. It rsyncs a locally built `dist` directory into
# the running container with `docker cp`, so a SPA missing from the image would still
# work in production while the image itself was broken — which is exactly the failure
# mode to catch after packaging changes (see the single-stage note in the Dockerfile).
# This runs the image with no compose file, no bind mounts and no post-copy, against a
# throwaway database, and checks the API and the SPA it ships.
#
# Read-only with respect to production: the container is temporary, namespaced by PID,
# and removed on exit. It does not touch the live containers, DB or volumes.

SERVER="${1:-medaiadm@medai-prod}"
IMAGE="${IMAGE:-gazzali:prod}"
SSH="ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=4 ${SERVER}"
NAME="gazzali-smoke-$$"
PORT="${PORT:-17861}"

cleanup() {
    ${SSH} "docker rm -f ${NAME} >/dev/null 2>&1" || true
}
trap cleanup EXIT

echo "╔══════════════════════════════════════════════════╗"
echo "║     Gazzali — image smoke test                ║"
echo "╚══════════════════════════════════════════════════╝"
echo "Server: ${SERVER}   Image: ${IMAGE}"

fail() { echo "  ✗ $1"; echo ""; echo "SMOKE TEST FAILED: $1"; exit 1; }

# ── Start the image alone ────────────────────────────────────────────────
echo "[1/5] Starting the image with no compose file, no docker cp..."
${SSH} "docker rm -f ${NAME} >/dev/null 2>&1 || true"
${SSH} "docker run -d --name ${NAME} -p 127.0.0.1:${PORT}:7860 \
    -e GAZZALI_PM_DB=/tmp/smoke.db -e GAZZALI_DATA_DIR=/tmp/smoke-data \
    ${IMAGE} --host 0.0.0.0 >/dev/null" || fail "container would not start"

# ── Health ───────────────────────────────────────────────────────────────
echo "[2/5] Waiting for the API to answer..."
HEALTHY=0
for i in $(seq 1 45); do
    CODE=$(${SSH} "curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:${PORT}/api/v1/health" || true)
    if [ "${CODE}" = "200" ]; then HEALTHY=1; echo "  ✓ /api/v1/health 200 after ${i}s"; break; fi
    sleep 1
done
if [ "${HEALTHY}" != "1" ]; then
    echo "  --- last 20 log lines ---"
    ${SSH} "docker logs --tail 20 ${NAME}" || true
    fail "the API never became healthy (last status: ${CODE:-none})"
fi

# ── SPA shell ────────────────────────────────────────────────────────────
echo "[3/5] Checking the SPA the image ships..."
INDEX=$(${SSH} "curl -s --max-time 5 http://127.0.0.1:${PORT}/" || true)
echo "${INDEX}" | grep -q 'id="root"' || fail "index.html was not served (found: $(echo "${INDEX}" | head -c 120))"
BUNDLE=$(echo "${INDEX}" | grep -o 'assets/index-[A-Za-z0-9_-]*\.js' | head -1)
[ -n "${BUNDLE}" ] || fail "index.html references no bundle — the dist directory is missing from the image"
echo "  ✓ index.html served, references ${BUNDLE}"

BUNDLE_CODE=$(${SSH} "curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:${PORT}/${BUNDLE}" || true)
[ "${BUNDLE_CODE}" = "200" ] || fail "the referenced bundle did not download (HTTP ${BUNDLE_CODE})"
echo "  ✓ bundle downloads (HTTP 200)"

# A client-side route must fall back to index.html rather than 404.
ROUTE_CODE=$(${SSH} "curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:${PORT}/login" || true)
[ "${ROUTE_CODE}" = "200" ] || fail "SPA route /login did not fall back to index.html (HTTP ${ROUTE_CODE})"
echo "  ✓ SPA route /login serves the shell"

# ── Packaging hygiene ────────────────────────────────────────────────────
echo "[4/5] Checking packaging hygiene..."
USER_ID=$(${SSH} "docker exec ${NAME} id -u" | tr -d '\r')
[ "${USER_ID}" = "1000" ] || fail "container runs as uid ${USER_ID}, expected the non-root 1000"
echo "  ✓ runs as the non-root user (uid 1000)"

SRC_FILES=$(${SSH} "docker exec ${NAME} sh -c 'find /src -type f 2>/dev/null | wc -l'" | tr -d '\r')
[ "${SRC_FILES}" = "0" ] || fail "/src still holds ${SRC_FILES} files — the build tree leaked into the image"
echo "  ✓ no build tree (/src) in the image"

echo "[5/5] Tearing down..."
cleanup
trap - EXIT
echo "  ✓ temporary container removed"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ✅  Smoke test passed: the image serves the app  ║"
echo "╚══════════════════════════════════════════════════╝"
