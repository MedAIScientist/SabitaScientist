#!/usr/bin/env bash
set -euo pipefail

# ── EvoScientist Production Setup ─────────────────────────────────────────────
# Run once on a fresh VPS to bootstrap the deployment.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR"

echo "=== EvoScientist Production Setup ==="
echo ""

# ── 1. Environment file ────────────────────────────────────────────────────────
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[1/5] Created .env — edit it with your API keys: vim .env"
else
    echo "[1/5] .env already exists"
fi

if [ ! -f deploy/.env ]; then
    cp deploy/.env.example deploy/.env
    echo "      Created deploy/.env — edit S3 credentials: vim deploy/.env"
fi

# ── 2. SSL certificates ────────────────────────────────────────────────────────
SSL_DIR="$SCRIPT_DIR/nginx/ssl"
if [ ! -f "$SSL_DIR/cert.pem" ]; then
    mkdir -p "$SSL_DIR"
    echo "[2/5] SSL certificates not found."
    echo "      Options:"
    echo "        a) Let's Encrypt (requires domain):"
    echo "           sudo apt install certbot && sudo certbot certonly --standalone \\"
    echo "             -d your-domain.com"
    echo "           sudo cp /etc/letsencrypt/live/your-domain.com/{fullchain.pem,privkey.pem} $SSL_DIR/"
    echo "           sudo chown \$USER:\$USER $SSL_DIR/*.pem"
    echo "        b) Self-signed (for testing, not prod):"
    echo "           openssl req -x509 -nodes -days 365 -newkey rsa:2048 \\"
    echo "             -keyout $SSL_DIR/key.pem \\"
    echo "             -out $SSL_DIR/cert.pem \\"
    echo "             -subj '/CN=localhost'"
    echo "      Then re-run this script."
else
    echo "[2/5] SSL certificates found"
fi

# ── 3. Validate Docker ─────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "[3/5] ERROR: Docker not found. Install Docker first:"
    echo "      curl -fsSL https://get.docker.com | sh"
    exit 1
fi
if ! docker compose version &>/dev/null; then
    echo "[3/5] ERROR: docker compose plugin not found."
    echo "      Install: sudo apt install docker-compose-plugin"
    exit 1
fi
echo "[3/5] Docker + compose found"

# ── 4. Build and start ─────────────────────────────────────────────────────────
echo "[4/5] Building images (first time may take several minutes)..."
docker compose -f deploy/docker-compose.yml build

echo "      Starting services..."
if [ -f "$SSL_DIR/cert.pem" ] && [ -f "$SSL_DIR/key.pem" ]; then
    docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.ssl.yml up -d
    echo "      HTTPS enabled"
else
    docker compose -f deploy/docker-compose.yml up -d
    echo "      HTTP only (no SSL certs found)"
fi

# ── 5. Initialize Garage ───────────────────────────────────────────────────────
echo "[5/5] Initializing Garage S3..."
sleep 3

ACCESS_KEY="${GARAGE_ACCESS_KEY:-GK1234567890abc}"
SECRET_KEY="${GARAGE_SECRET_KEY:-abcdef1234567890abcdef1234567890}"
BUCKET="${GARAGE_BUCKET:-evoscientist}"

# Configure Garage if not already done (expects curl in the container)
docker compose -f deploy/docker-compose.yml exec -T garage \
    garage layout assign -z dc1 -c /etc/garage.toml "$(cat /dev/urandom | head -c 32 | base64)" 2>/dev/null || true
docker compose -f deploy/docker-compose.yml exec -T garage \
    garage layout apply -c /etc/garage.toml 2>/dev/null || true

# Create access key and bucket
docker compose -f deploy/docker-compose.yml exec -T garage \
    garage key create -c /etc/garage.toml --name evoscientist "$ACCESS_KEY" 2>/dev/null || true
docker compose -f deploy/docker-compose.yml exec -T garage \
    garage bucket create -c /etc/garage.toml "$BUCKET" 2>/dev/null || true
docker compose -f deploy/docker-compose.yml exec -T garage \
    garage bucket allow -c /etc/garage.toml "$BUCKET" --owner --key "$ACCESS_KEY" 2>/dev/null || true

echo ""
echo "=== Setup Complete ==="
echo "    PM Dashboard:     http://$(curl -s ifconfig.me 2>/dev/null || echo 'localhost')"
echo "    API Health:       http://localhost:7860/api/v1/health"
echo ""
echo "    Next steps:"
echo "      1. Fill in API keys: vim .env"
echo "      2. Restart:   docker compose -f deploy/docker-compose.yml restart"
echo "      3. View logs: docker compose -f deploy/docker-compose.yml logs -f"
