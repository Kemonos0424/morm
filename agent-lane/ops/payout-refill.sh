#!/bin/bash
# payout-refill.sh — treasury(producer.seed) → PLAY/DASH payout 口座を TARGET 残高まで補充する。
#
#   ★★ 資金移動（実MORM送金）を伴う。自動化(cron)で回すかはユーザー判断。★★
#   Mac Mini(L1 と ~/.morm-l1/producer.seed のある機)でのみ動作。base=1（amount は整数MORM）。
#   ★seed は MORM_SUBMIT_SEED env で渡す(argv/`ps` に平文を出さない)。
#
#   使い方:
#     ./payout-refill.sh              # 両口座を TARGET まで補充（不足分のみ）
#     ./payout-refill.sh PLAY         # PLAY のみ
#   env:
#     MORM_L1_RPC     既定 http://127.0.0.1:8900
#     PAYOUT_TARGET   目標残高（既定 100000 MORM）
#     MORM_L1_DIR     morm_l1 が import できる dir（既定 ~/morm-l1）
#     REFILL_WAIT_MAX 着金待ちの上限秒（既定 90・超過で異常終了=無限ループ回避）
set -uo pipefail
RPC="${MORM_L1_RPC:-http://127.0.0.1:8900}"
TARGET="${PAYOUT_TARGET:-100000}"
L1DIR="${MORM_L1_DIR:-$HOME/morm-l1}"
WAIT_MAX="${REFILL_WAIT_MAX:-90}"
SEEDFILE="$HOME/.morm-l1/producer.seed"
declare -A ADDR=( [PLAY]=m0r3pos24vwa5d3lq5vqaij75wo3tmyrv4t [DASH]=m0roshqbpskljwuj3drophhb7tth33qprzn )
which=("$@"); [ $# -eq 0 ] && which=(PLAY DASH)

# 残高取得。RPC/parse 失敗は "ERR" を返す(set -e で黙って落ちない)。
bal() {
  local out
  out="$(curl -s --max-time 8 "$RPC/account/$1" 2>/dev/null | python3 -c 'import sys,json
try: print(int(json.load(sys.stdin).get("balance",0)))
except Exception: print("ERR")' 2>/dev/null)"
  [ -z "$out" ] && out="ERR"
  printf '%s' "$out"
}

[ -f "$SEEDFILE" ] || { echo "[refill] fatal: $SEEDFILE not found"; exit 1; }
export MORM_SUBMIT_SEED="$(cat "$SEEDFILE")"   # ★env で渡す(argv 露出回避)
rc=0
for name in "${which[@]}"; do
  addr="${ADDR[$name]:-}"; [ -z "$addr" ] && { echo "[refill] unknown account: $name"; rc=1; continue; }
  cur="$(bal "$addr")"
  if [ "$cur" = "ERR" ]; then echo "[refill] $name: RPC/parse error → skip"; rc=1; continue; fi
  if [ "$cur" -ge "$TARGET" ]; then echo "[refill] $name=$cur >= target $TARGET → skip"; continue; fi
  need=$(( TARGET - cur ))
  echo "[refill] $name=$cur → transfer $need (target $TARGET)"
  if ! ( cd "$L1DIR" && python3 -m morm_l1.cli submit --rpc "$RPC" transfer --to "$addr" --amount "$need" ); then
    echo "[refill] $name: submit failed → skip (再実行で再試行)"; rc=1; continue
  fi
  # 着金（＝treasury nonce 前進）を上限つきで待つ。超過＝異常(無限ループ回避)。連投は nonce 衝突なので次口座前に待つ。
  waited=0
  while :; do
    b="$(bal "$addr")"
    [ "$b" != "ERR" ] && [ "$b" -ge "$TARGET" ] && { echo "[refill] $name now $b"; break; }
    waited=$(( waited + 2 )); sleep 2
    if [ "$waited" -ge "$WAIT_MAX" ]; then
      echo "[refill] $name: TIMEOUT ${WAIT_MAX}s 未着(tx drop/RPC異常?) → abort"; exit 2
    fi
  done
done
exit $rc
