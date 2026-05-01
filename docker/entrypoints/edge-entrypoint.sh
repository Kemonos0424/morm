#!/bin/sh
# MORM Edge entrypoint (origin or mirror).
#
# Required env:
#   ROLE                — "origin" or "mirror"
#   NODE_ID             — unique label, default "edge-0"
# Optional env:
#   EDGE_PORT           — default 8787
#   PEERS               — comma-separated peer URLs
#   ORIGIN_DB           — origin only; default /data/edge/morm.db
set -eu

EDGE_PORT="${EDGE_PORT:-8787}"
NODE_ID="${NODE_ID:-edge-0}"
ROLE="${ROLE:-mirror}"

ARGS="--host 0.0.0.0 --port $EDGE_PORT --node-id $NODE_ID --role $ROLE \
      --storage-dir /data/edge/$NODE_ID"

if [ "$ROLE" = "origin" ]; then
    DB="${ORIGIN_DB:-/data/edge/morm.db}"
    mkdir -p "$(dirname "$DB")"
    if [ ! -f "$DB" ]; then
        echo "[edge] origin DB missing at $DB — touching empty file (real schema bootstraps via morm-core CLI)"
        : > "$DB"
    fi
    ARGS="$ARGS --db $DB"
fi

[ -n "${PEERS:-}" ] && ARGS="$ARGS --peers $PEERS"

mkdir -p "/data/edge/$NODE_ID"

echo "[edge] python morm-player/server.py $ARGS"
exec python /app/morm-player/server.py $ARGS
