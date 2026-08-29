# 並列レビュー findings と対応（2026-08-29）

4体の read-only レビュー（settle/payout・read-path security・Agent Lane 経済・ops/config）の結果。

## ✅ 修正・本番反映済み

| # | 重大度 | 内容 | commit / 反映 |
|---|---|---|---|
| A | **CRITICAL** | **本番 ADMIN_TOKEN 公開露出**: git-tracked(PUBLIC)の `adm_1b3…` が本番 play の生 token。全 `/api/admin/*`(payout/settle/moderation)が全世界に開放 | tracked除去 `2819ed8`／ユーザーが plist token ローテ＋**bootout+bootstrap** で反映→旧token 403 確認 |
| B | **CRITICAL** | **proportional 過剰発行**: 部分完了/手動二重呼び/crash後 re-fire で B_units を ΣP に再分割→総発行が予算超過 | `be92c8b`：エポック間隔ガード＋開始時予約記録(検証8/8)。Play 本番反映 |
| C | **HIGH** | **view-farm→drain**: 未署名 view の dedup/レート鍵が client 任意 uid→uid ローテで偽 view 量産→views×VIEW_RATE→payout | `be92c8b`：未署名は IP 鍵に束ねる。Play 反映 |
| D | HIGH | **payout-refill 無限ループ＋seed argv 露出** | `dbbfe6e`：着金待ち有界化(REFILL_WAIT_MAX)・`MORM_SUBMIT_SEED` env・cli 対応・bash3.2互換 |
| E | MEDIUM | **_proxy パストラバーサル/SSRF**: `rest` 無サニタイズ | `be92c8b`：`..`/バックスラッシュ拒否＋安全 charset。Play 反映 |
| F | MEDIUM | **bridge-valve fail-open**: checkBurn 例外で bypass | `b19839e`：VALVE=on 時は例外→503(fail-closed)。Vercel 反映 |
| G | MEDIUM | **emit-nodes 未 inert**: admin token だけで 1500 MORM/epoch | `b19839e`：`NODE_EMISSION_ENABLED!=on`(既定)なら 410。Vercel 反映(410確認) |
| H | MEDIUM | **lane/earn 予約残り**: 送金失敗で ref 恒久 unclaimable | `b19839e`：`releaseEarn` で失敗時解放(確定行は削除せず二重払い防止) |
| — | 運用罠 | **launchd env は kickstart で再読込されない**(bootout+bootstrap 必須) | handoff 罠に記録。今回の play env 全変更を bootout で反映確定 |

## ✅ 追加修正（レビュー後・本番反映済 第2波）

| # | 重大度 | 内容 | commit |
|---|---|---|---|
| I | **HIGH** | **システム発行上限なし**→register/faucet/lane-earn 共有の日次発行上限(`app/lib/issuance.js`・morm_txs 24h合計・既定10000 MORM/env `MORM_DAILY_ISSUANCE_CAP`)。Vercel 反映 | `d04b08d` |
| J | MEDIUM | **AGE_SECRET を ADMIN_TOKEN から独立化**(`AGE_SECRET_KEY`優先→無ければ token→空なら起動毎ランダム)。既知定数での age cookie 偽造を封鎖 | `3410efc` |
| K | LOW-MED | **未承認メタ漏洩**: `/api/content/{id}` を status で 404 化(未承認はメタも隠す)。Play 反映 | `3410efc` |

## 設計系 findings — 判断結果（2026-08-29）

- ✅**[MEDIUM] payout() atomic claim → 実装済 `1333a71`**: 予約を CAS(earnings が読んだ paid を条件に
  条件付き UPDATE / PK INSERT・rowcount0/PK衝突で concurrent skip)化。単一プロセスは `_payout_lock` で
  既に安全だが多重プロセス/blue-green でも安全側。テスト4項目PASS・Play 本番反映。
- ⏸**[MEDIUM] 署名read が pub 秘匿依存 → 据置(ユーザー判断 2026-08-29)**: 実務上の危険度が低い(被害者の
  署名POST 観測=悪性拡張/POSTボディログ/侵害クライアントが必要・HTTPS上で remote無認証攻撃ではない)一方、
  正しい修正は www `account.html` と play `index.html` の2クライアント協調改修＋read replay 窓対策が要り
  live walletUI を壊すリスクが高い。additive(?pub= 併存)では脆弱性が閉じない。
  **移行計画(実施時)**: ①サーバに signed-read(kind=account.read・nonce+短expiry・消費済nonce追跡)を additive 追加
  →②2クライアントを signed POST に移行→③検証後に `?pub=` GET を撤去(ここで初めて脆弱性が閉じる)。別ミニプロジェクトで。
- ⏸**[LOW] 署名replay(write) → 据置**: write は概ね冪等(like/follow/watch/comment)で replay 実害ほぼなし。
  全 write に nonce 追跡を足すのは低価値×高リスク。nonce の主価値は上記 signed-read 側にあるのでそこと一体で。
- **[LOW] その他(据置)**: pending マーカーの sweeper(照合バッチ)／admin の constant-time 比較／
  base=1↔1e6 時の morm_txs.amount 表記／story/comments の status フィルタ。

## 参考
- 詳細な再現・行番号は各レビュー結果（本セッション transcript）。secret ローテ=`SECURITY-SECRET-ROTATION.md`。
