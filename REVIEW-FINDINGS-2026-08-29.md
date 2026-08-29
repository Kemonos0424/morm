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

## ⚠️ 未対応（要判断/設計・ドキュメント化）

- **[HIGH] システム全体の発行上限なし**（register/faucet/lane-earn が DASH から無制限に引ける・sybil で供給インフレ）。
  現状 **cash-out valve(fail-closed 化済)が fiat 出口を絞る**ため急性 drain は緩和されるが、内部供給インフレは残る。
  **推奨**: register+faucet+lane-earn 共有の日次発行台帳＋上限(env 可変)を追加、faucet/lane を passkey 実証で gate、
  register を IP レート制限(ip_hash は保存済で未チェック)。**上限値は経済判断＝ユーザー決定**。
- **[MEDIUM] AGE_SECRET が ADMIN_TOKEN 由来**: ADMIN_TOKEN 未設定だと age cookie 偽造可（現在は token 設定済で不成立）。
  独立の `AGE_SECRET_KEY` env にし、未設定なら R18 無効化/起動拒否が望ましい。
- **[MEDIUM] payout() は atomic DB claim なし**（単一プロセスなら安全。多重プロセス/blue-green で二重払い）。
  他3経路と同型の条件付き UPDATE + rowcount を入れるか、単一プロセス運用を明文化。
- **[MEDIUM] 署名read が pub 秘匿依存**: earnings/mine/me は `?pub=` で認証。pub は署名POSTで広く送信されるため、
  観測で漏れると他者の収益が読める。nonce+expiry の署名read に上げるのが理想。
- **[LOW-MEDIUM] 未承認メタ漏洩**: `/api/content/{id}`・`/api/story`・`/api/comments` が status 無フィルタ。
  owner/admin 用パスと分けて `status IN('approved','shadow')` を追加（owner が自分の pending を見る動線に注意）。
- **[LOW] 署名replay(nonce/expiry なし)**／**pending マーカーの sweeper なし**／constant-time 比較／base=1↔1e6 の morm_txs.amount 表記。

## 参考
- 詳細な再現・行番号は各レビュー結果（本セッション transcript）。secret ローテ=`SECURITY-SECRET-ROTATION.md`。
