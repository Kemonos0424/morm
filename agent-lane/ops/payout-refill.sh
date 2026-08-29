#!/bin/bash
# payout-refill.sh — treasury(producer.seed) → PLAY/DASH payout 口座を TARGET 残高まで補充する。
#
#   ★★ 資金移動（実MORM送金）を伴う。自動化(cron)で回すかはユーザー判断。★★
#   Mac Mini(L1 と ~/.morm-l1/producer.seed のある機)でのみ動作。base=1（amount は整数MORM）。
#
#   使い方:
#     ./payout-refill.sh              # 両口座を TARGET まで補充（不足分のみ）
#     ./payout-refill.sh PLAY         # PLAY のみ
#   env:
#     MORM_L1_RPC   既定 http://127.0.0.1:8900
#     PAYOUT_TARGET 目標残高（既定 100000 MORM）
#     MORM_L1_DIR   morm_l1 が import できる dir（既定 ~/morm-l1）
set -eu
RPC="${MORM_L1_RPC:-http://127.0.0.1:8900}"
TARGET="${PAYOUT_TARGET:-100000}"
L1DIR="${MORM_L1_DIR:-$HOME/morm-l1}"
SEEDFILE="$HOME/.morm-l1/producer.seed"
declare -A ADDR=( [PLAY]=m0r3pos24vwa5d3lq5vqaij75wo3tmyrv4t [DASH]=m0roshqbpskljwuj3drophhb7tth33qprzn )
which=("${1:-PLAY}" "${2:-DASH}"); [ $# -ge 1 ] && which=("$@")

bal() { curl -s --max-time 8 "$RPC/account/$1" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("balance",0))'; }

for name in "${which[@]}"; do
  addr="${ADDR[$name]:-}"; [ -z "$addr" ] && { echo "unknown account: $name"; continue; }
  cur="$(bal "$addr")"
  if [ "$cur" -ge "$TARGET" ]; then echo "[refill] $name=$cur >= target $TARGET → skip"; continue; fi
  need=$(( TARGET - cur ))
  echo "[refill] $name=$cur → transfer $need (target $TARGET)"
  ( cd "$L1DIR" && python3 -m morm_l1.cli submit --rpc "$RPC" --seed "$(cat "$SEEDFILE")" transfer --to "$addr" --amount "$need" )
  # 着金（＝treasury nonce 前進）を待ってから次口座（cli submit は着金確認しないため連投で nonce 衝突）
  until [ "$(bal "$addr")" -ge "$TARGET" ]; do sleep 1; done
  echo "[refill] $name now $(bal "$addr")"
done
