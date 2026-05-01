#!/usr/bin/env bash
# Phase 30d — MORM federated node one-line installer.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/<gh-user>/morm/main/docker/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/<gh-user>/morm/main/docker/install.sh | MORM_DIR=/srv/morm bash
#
# What it does:
#   1. Checks docker + docker compose are present (otherwise prints how to install)
#   2. Clones (or pulls) the morm repo to $MORM_DIR (default ~/morm)
#   3. Generates producer + treasury keys via docker/init.sh (idempotent)
#   4. `docker compose pull` to fetch ghcr.io images, then `up -d`
#   5. Tails healthchecks until the gateway responds, then prints the URL
#
# Re-runs are safe — keys/data persist across `up -d`s.

set -euo pipefail

MORM_DIR="${MORM_DIR:-$HOME/morm}"
GITHUB_USER="${GITHUB_USER:-Kemonos0424}"      # default repo owner
BRANCH="${BRANCH:-main}"
GATEWAY_PORT="${GATEWAY_PORT:-8801}"

C_BLUE="\033[1;34m"; C_GREEN="\033[1;32m"; C_RED="\033[1;31m"; C_DIM="\033[2m"; C_RST="\033[0m"
say()   { printf "${C_BLUE}[install]${C_RST} %s\n" "$*"; }
warn()  { printf "${C_RED}[install]${C_RST} %s\n" "$*" >&2; }
ok()    { printf "${C_GREEN}[install]${C_RST} %s\n" "$*"; }

# ---- 1. Docker check ---------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    warn "Docker is not installed."
    cat <<-EOF
    Install Docker first:
      macOS:    https://docs.docker.com/desktop/install/mac-install/
      Linux:    curl -fsSL https://get.docker.com | sh
      Windows:  https://docs.docker.com/desktop/install/windows-install/
    Then re-run this script.
EOF
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    warn "Docker is installed but the daemon is not running."
    echo "    macOS:   open -a Docker"
    echo "    Linux:   sudo systemctl start docker"
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    warn "docker compose plugin missing. Update Docker Desktop or install:"
    echo "    sudo apt-get install docker-compose-plugin   # Ubuntu/Debian"
    exit 1
fi

ok "Docker + Compose detected: $(docker --version), $(docker compose version --short)"

# ---- 2. Source tree ----------------------------------------------------
if [ -d "$MORM_DIR/.git" ]; then
    say "Updating existing repo at $MORM_DIR"
    git -C "$MORM_DIR" fetch --quiet origin "$BRANCH"
    git -C "$MORM_DIR" checkout --quiet "$BRANCH"
    git -C "$MORM_DIR" pull --quiet --ff-only origin "$BRANCH"
elif [ -d "$MORM_DIR" ] && [ "$(ls -A "$MORM_DIR" 2>/dev/null || true)" ]; then
    warn "$MORM_DIR exists and is not a git repo. Refusing to overwrite. Set MORM_DIR= to a different path."
    exit 1
else
    say "Cloning https://github.com/$GITHUB_USER/morm into $MORM_DIR"
    git clone --quiet --branch "$BRANCH" \
        "https://github.com/$GITHUB_USER/morm.git" "$MORM_DIR"
fi
ok "Source ready: $MORM_DIR"

# ---- 3. Initial keys ---------------------------------------------------
cd "$MORM_DIR"
if [ -f docker/init.sh ]; then
    say "Generating / reusing producer + treasury keys"
    bash docker/init.sh
else
    warn "docker/init.sh missing in $MORM_DIR — repo layout out of sync"
    exit 1
fi

# ---- 4. Pull + up ------------------------------------------------------
COMPOSE="docker compose -f $MORM_DIR/docker/morm-node.docker-compose.yml --env-file $MORM_DIR/docker/.env"
say "Pulling images from ghcr.io"
$COMPOSE pull --quiet || warn "pull failed; will fall back to local build below if images aren't on ghcr yet"

say "Starting stack (l1 + gateway + edge)"
$COMPOSE up -d

# ---- 5. Wait for health ------------------------------------------------
say "Waiting for gateway healthcheck to pass…"
attempts=0
until curl -fsS "http://127.0.0.1:$GATEWAY_PORT/api/morm/info" >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "$attempts" -gt 60 ]; then
        warn "Gateway did not come up after 60 attempts. Check logs:"
        echo "    $COMPOSE logs --tail=100"
        exit 1
    fi
    sleep 2
done

cat <<EOF

${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RST}
${C_GREEN} MORM federated node is up.${C_RST}
${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RST}

  Gateway:   http://localhost:$GATEWAY_PORT/auth-morm     (passkey signup)
             http://localhost:$GATEWAY_PORT/wallet         (policy manager)
             http://localhost:$GATEWAY_PORT/swap           (bridge UI, if configured)

  L1 RPC:    http://localhost:8900/info
  Edge:      http://localhost:8787/

  Producer addr:  $(cat "$MORM_DIR/docker/data/l1/producer.address" 2>/dev/null || echo '?')
  Treasury addr:  $(cat "$MORM_DIR/docker/data/gateway/treasury.address" 2>/dev/null || echo '?')

  Logs:           $COMPOSE logs -f
  Stop:           $COMPOSE down
  Update:         curl -fsSL https://raw.githubusercontent.com/$GITHUB_USER/morm/$BRANCH/docker/install.sh | bash

${C_DIM}First-time? Visit http://localhost:$GATEWAY_PORT/auth-morm to create a passkey,
then http://localhost:$GATEWAY_PORT/wallet to see your default per-app policies.${C_RST}

EOF
