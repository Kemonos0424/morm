#!/usr/bin/env bash
# MORM Phase 22 — install + configure coturn (macOS Homebrew or Linux apt).
#
# Usage:
#   ops/turn/install-coturn.sh \
#       --external-ip 203.0.113.10 \
#       --realm morm.local \
#       [--secret <hex>]            # generated if omitted
#       [--min-port 49160] [--max-port 49200]
#
# Outputs:
#   - /opt/homebrew/etc/turnserver.conf   (macOS) or /etc/turnserver.conf (Linux)
#   - prints the secret to stdout (use it as passkey_morm.py --turn-secret)
#   - on macOS: starts via `brew services start coturn`
#   - on Linux: enables + starts the systemd unit
set -euo pipefail

EXT_IP=""
REALM="morm.local"
SECRET=""
MIN_PORT=49160
MAX_PORT=49200

while [[ $# -gt 0 ]]; do
  case "$1" in
    --external-ip) EXT_IP="$2"; shift 2 ;;
    --realm)       REALM="$2";  shift 2 ;;
    --secret)      SECRET="$2"; shift 2 ;;
    --min-port)    MIN_PORT="$2"; shift 2 ;;
    --max-port)    MAX_PORT="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$EXT_IP" ]]; then
  echo "error: --external-ip required (the public/LAN IP clients will reach)" >&2
  exit 2
fi
if [[ -z "$SECRET" ]]; then
  SECRET="$(openssl rand -hex 32)"
fi

HERE="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$HERE/turnserver.conf.template"

case "$(uname -s)" in
  Darwin)
    if ! command -v brew >/dev/null; then
      echo "Homebrew required on macOS" >&2; exit 1
    fi
    if ! brew list coturn >/dev/null 2>&1; then
      brew install coturn
    fi
    CONF="$(brew --prefix)/etc/turnserver.conf"
    # /opt/homebrew/etc is user-owned on macOS — no sudo needed.
    sed -e "s|__EXTERNAL_IP__|$EXT_IP|" \
        -e "s|__REALM__|$REALM|" \
        -e "s|__SECRET__|$SECRET|" \
        -e "s|__MIN_PORT__|$MIN_PORT|" \
        -e "s|__MAX_PORT__|$MAX_PORT|" "$TEMPLATE" > "$CONF"
    brew services restart coturn
    ;;
  Linux)
    if ! command -v turnserver >/dev/null; then
      sudo apt-get update && sudo apt-get install -y coturn
    fi
    CONF="/etc/turnserver.conf"
    sudo tee "$CONF" >/dev/null < <(
      sed -e "s|__EXTERNAL_IP__|$EXT_IP|" \
          -e "s|__REALM__|$REALM|" \
          -e "s|__SECRET__|$SECRET|" \
          -e "s|__MIN_PORT__|$MIN_PORT|" \
          -e "s|__MAX_PORT__|$MAX_PORT|" "$TEMPLATE"
    )
    if [[ -f /etc/default/coturn ]]; then
      sudo sed -i 's|^#TURNSERVER_ENABLED=1|TURNSERVER_ENABLED=1|' /etc/default/coturn
    fi
    sudo systemctl enable --now coturn
    ;;
  *)
    echo "unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac

cat <<EOF

coturn installed.
  config:        $CONF
  external-ip:   $EXT_IP
  realm:         $REALM
  relay ports:   ${MIN_PORT}-${MAX_PORT} (open on firewall)
  shared secret: $SECRET

next: pass the secret to the gateway:
  python passkey_morm.py \\
    --turn-url turn:${EXT_IP}:3478?transport=udp \\
    --turn-url turn:${EXT_IP}:3478?transport=tcp \\
    --turn-secret $SECRET

verify with:
  curl -s http://localhost:8801/api/signal/ice?peer_id=test | jq
  turnutils_uclient -y -u test -w \$(./hmac.sh $SECRET test) ${EXT_IP}
EOF
