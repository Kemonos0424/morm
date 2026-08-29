# payout 口座の補充 runbook（前提(1)の実作業）

支払い口座を treasury(genesis 1e18 保持=`~/.morm-l1/producer.seed`) から補充する。**本番 L1 を触る操作＝デプロイ時にユーザーが実行**。

## 生成済み口座（鍵はリポジトリ外・0600）
| 用途 | address | seed |
|---|---|---|
| PLAY_PAYOUT | `m0r3pos24vwa5d3lq5vqaij75wo3tmyrv4t` | `~/.morm-agentlane/play_payout.seed` |
| DASH_PAYOUT | `m0roshqbpskljwuj3drophhb7tth33qprzn` | `~/.morm-agentlane/dash_payout.seed` |

（addresses.json: `~/.morm-agentlane/addresses.json`）

## 補充（treasury → 各 payout 口座, kind:6）
Mac Mini（L1 と producer.seed のある機）で、**base=1 なら amount は MORM 整数**。例: 各 100000 MORM を補充。

```bash
# treasury seed（producer=treasury）
PLAY=m0r3pos24vwa5d3lq5vqaij75wo3tmyrv4t
DASH=m0roshqbpskljwuj3drophhb7tth33qprzn
cd ~/<morm-l1 のパス>   # morm_l1 が import できる場所
MORM_L1_RPC=http://127.0.0.1:8900
SEED=$(cat ~/.morm-l1/producer.seed)   # treasury seed(hex)

python3 -m morm_l1.cli submit --rpc "$MORM_L1_RPC" --seed "$SEED" transfer --to "$PLAY" --amount 100000
# ★1件目が採用(ブロック採用でtreasury nonce++)されるまで待ってから2件目（cli submitは着金確認しないため連投はnonce衝突）
until [ "$(curl -s $MORM_L1_RPC/account/$PLAY | python3 -c 'import sys,json;print(json.load(sys.stdin)["balance"])')" != "0" ]; do sleep 1; done
python3 -m morm_l1.cli submit --rpc "$MORM_L1_RPC" --seed "$SEED" transfer --to "$DASH" --amount 100000
```

- 着金確認: `curl -s $MORM_L1_RPC/account/$PLAY` / `$DASH` の balance。
- 以後は残高監視 → 下限割れで自動補充（cron で同じ transfer）。

## 重要
- **AD の redistribution 整合**: 広告主の入金は **DASH_PAYOUT 宛**（ad payout の署名者）に送ってもらい、その tx を `ad-campaign {action:fund, depositTx}` で記録する。こうすると DASH_PAYOUT が広告予算分だけ潤い、`settle` は発行でなく再分配になる。
- **nonce 独立**: PLAY_PAYOUT(=Play settle)・DASH_PAYOUT(=dashboard payout)・producer(=ブロック生成) が別鍵 → プロセス跨ぎでも nonce 衝突しない。
- seed は絶対に commit しない / 表示しない。
