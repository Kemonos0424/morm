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

## ⚠️ 残（単一プロセスでは安全 or 設計変更・ドキュメント化）

- **[MEDIUM] payout() は atomic DB claim なし**: 現状 **単一 ThreadingHTTPServer + `_payout_lock` で安全**。
  多重プロセス/blue-green を導入する場合のみ、他3経路と同型の条件付き UPDATE(CAS)+rowcount を追加すること。
- **[MEDIUM] 署名read が pub 秘匿依存**: earnings/mine/me は `?pub=` で認証。pub は署名POSTで広く送信されるため、
  観測で漏れると他者の収益が読める。nonce+expiry の**署名read**に上げるのが理想(設計変更)。
- **[LOW] 署名replay(nonce/expiry なし)**: 状態変更は概ね冪等。厳密化には消費済 nonce 追跡が要る(設計変更)。
- **[LOW] pending マーカーの sweeper なし**(reservation-first で残る 'pending' tx の照合バッチ)／
  admin の constant-time 比較／base=1↔1e6 時の morm_txs.amount 表記／story/comments の status フィルタ。

## 参考
- 詳細な再現・行番号は各レビュー結果（本セッション transcript）。secret ローテ=`SECURITY-SECRET-ROTATION.md`。
