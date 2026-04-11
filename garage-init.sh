#!/usr/bin/env bash
# One-time Garage bootstrap: create layout, bucket, and access key.
# Run this AFTER `docker compose up -d` and garage is healthy.
set -euo pipefail

GARAGE_CLI="docker compose exec garage /garage"
BUCKET="${GARAGE_BUCKET:-evoscientist}"

echo "==> Applying Garage layout (single node, capacity 1)..."
NODE_ID=$($GARAGE_CLI status 2>/dev/null | grep 'NO ROLE' | awk '{print $1}' | head -1)
if [ -z "$NODE_ID" ]; then
  echo "Garage already has a layout. Skipping layout apply."
else
  $GARAGE_CLI layout assign -z dc1 -c 1G "$NODE_ID"
  $GARAGE_CLI layout apply --version 1
fi

echo "==> Creating bucket '${BUCKET}'..."
$GARAGE_CLI bucket create "${BUCKET}" 2>/dev/null || echo "Bucket already exists."
$GARAGE_CLI bucket allow --read --write --owner "${BUCKET}" 2>/dev/null || true

echo "==> Creating access key 'evoscientist-app'..."
KEY_OUTPUT=$($GARAGE_CLI key create "evoscientist-app" 2>/dev/null || $GARAGE_CLI key list | grep evoscientist-app)
echo "$KEY_OUTPUT"

echo ""
echo "==> Done! Copy the Key ID and Secret Key above into your .env file:"
echo "    GARAGE_ACCESS_KEY=<Key ID>"
echo "    GARAGE_SECRET_KEY=<Secret Key>"
