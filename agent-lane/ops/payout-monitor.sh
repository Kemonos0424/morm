#!/bin/bash
# payout-monitor.sh — PLAY/DASH payout 口座の残高を監視し、下限割れを ALERT する（READ-ONLY・資金移動なし）。
# Mac Mini(L1と同機)で cron 実行想定。ログ=~/.morm-agentlane/payout-monitor.log
#
#   env:
#     MORM_L1_RPC          既定 http://127.0.0.1:8900
#     PAYOUT_MIN_BALANCE   これ未満で ALERT（既定 10000 MORM）
#
# refill（treasury→payout の補充）は payout-refill.sh（資金移動＝手動/ユーザー判断で有効化）。
set -u
RPC="${MORM_L1_RPC:-http://127.0.0.1:8900}"
THRESHOLD="${PAYOUT_MIN_BALANCE:-10000}"
PLAY=m0r3pos24vwa5d3lq5vqaij75wo3tmyrv4t
DASH=m0roshqbpskljwuj3drophhb7tth33qprzn
TS="$(date '+%Y-%m-%d %H:%M:%S')"
rc=0
for pair in "PLAY:$PLAY" "DASH:$DASH"; do
  name="${pair%%:*}"; addr="${pair##*:}"
  bal="$(curl -s --max-time 8 "$RPC/account/$addr" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("balance",0))' 2>/dev/null || echo ERR)"
  if [ "$bal" = "ERR" ]; then echo "$TS [payout-monitor] $name RPC_ERROR ($RPC)"; rc=1; continue; fi
  if [ "$bal" -lt "$THRESHOLD" ]; then
    echo "$TS [payout-monitor] ALERT $name balance=$bal < $THRESHOLD → refill needed (payout-refill.sh $name)"; rc=2
  else
    echo "$TS [payout-monitor] OK    $name balance=$bal"
  fi
done
exit $rc
