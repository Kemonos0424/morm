# Agent Lane — 本番デプロイ計画

原則: **全フラグ既定 off＝現行挙動**。まず「不活性コード」を本番に出し（挙動ゼロ変化）、その後フラグを**段階的に**立てる。各段は独立に**即ロールバック可**（フラグを戻すだけ）。フラグ一覧＝`MANIFEST.md`。

---

## ★★ 2026-08-29 確定更新（この節が最優先・以降の記述を上書き）★★

**背景**: 本DEPLOY.md初版(2026-08-26)以降、**ノード運用者の実ダッシュボード＆報酬が別アプリ node.morm.one（`~/Desktop/node-cluster/src/node-dashboard`／Vercel `node-dashboard`／別Turso `node-dashboard-kemonos0424`）に移行**した。node.morm.one は報酬を **`earned = 稼働時間×0.5 + 実利用GB×0.1`（`app/lib/reward.js` → `/api/admin/morm-distribute` → `scripts/morm-payout.py`）** で実払いしている（2026-08-29 稼働・整備済）。api.morm.one(morm-dashboard) の `nodes` は**旧世代（別DB・0xウォレット）**で、live のMCノードとは別population。

**確定した統合モデル（ユーザー承認 2026-08-29）**:
1. **ノード報酬 = node.morm.one の earned が唯一の正**。**⑤ node-emission / `/api/admin/emit-nodes` / Phase E は退役・活性化しない**。有効化すると①旧DBの別ノードへ空配布 or ②同一ノードへ二重支払いになる。§22(A)「ノード報酬を emit-nodes に一本化」は**撤回・無効**。
2. **Agent Lane（airdrop）が担うのは「ノード以外の3トラック」のみ**: ①AIエージェント lane(`/api/lane/*`) ②Play engagement(比例配分/view) ③AD(発行外)。node は airdrop の B_epoch 比例配分に**含めない**。
3. **B_epoch の split 再正規化**: `SPLIT_NODE` は**使わない**（0にする）。engagement は `SPLIT_ENGAGE` のまま、余った配分は reserve へ（発行が B を超えない前提は維持）。
4. **紐付け**: 4トラックとも m0r ウォレットへ着金＝**account.html（www.morm.one）が共通の残高/履歴UI**。payout鍵は分離済（`~/.morm-agentlane/` の PLAY_PAYOUT/DASH_PAYOUT）。

**セキュリティ状態（2026-08-29 反映済）**:
- ✅ api.morm.one `/api/admin/send` の**無認証treasury drain封鎖**＋admin既定`1234`撤廃（fail-closed）。node.morm.one `/api/admin/morm-distribute`・`ops/summary` も認証化。詳細=メモリ `reference_morm_security_audit_2026-08`。
- ⚠️ 上記で **api.morm.one は `ADMIN_PASSWORD` 未設定だと admin系（ad-campaign 等）が拒否**。AD(Phase F)前に Vercel env 設定が必須（＝旧計画の「1234撤廃」は実施済、あとは強い値を設定するだけ）。
- ⚠️ Play `payout()` は予約先行+lockに修正済（二重支払い回避）。**他4 settle経路は未修正**＝engagement(Phase D)活性化前に同パターン適用＋`verify/run_all.sh`必須。

**検証**: `verify/run_all.sh` = **9/9 PASS（2026-08-29 実チェーン再確認済）**。実装は健全。

**改訂後の推奨順序**: A(不活性+鍵分離+admin強化) → **C(バルブ先行)** → F(AD・発行外で安全) → B(lane・cap必須) → D(engagement・要play settle修正) → 〔後日〕G(base=1e6)。**Phase E(node) は廃止**。

---

## 0. デプロイ対象は2つ
| 対象 | 実体 | 出し方 |
|---|---|---|
| morm-dashboard | Vercel（api.morm.one） | git push → Vercel deploy |
| morm-play | Mac Mini launchd `com.morm.play`（play.morm.one, PLAY_PORT=8791） | play_server.py 転送 → サービス再起動 |

L1本体（Mac Mini 127.0.0.1:8900）は不変。決済経路は既存のまま。

---

## ★ 事前に必ず潰す2つの前提（設計上の要）

### (1) クロスプロセス treasury nonce 競合 ← 最重要
kind6 送金は**誰でも可**（treasury限定ではない）。今は Play(`l1_transfer`, seed=`~/.morm-l1/producer.seed`) と dashboard(`transferMorm`, `MORM_TREASURY_SEED`) が **同じ treasury 鍵**なら、別プロセスから同一口座の nonce を読む→**衝突して片方ドロップ**。各プロセス内の直列化(mutex/_l1_lock)は**プロセス間を跨がない**。
→ **対策（推奨）: 支払い口座をサービス別に分ける**。treasury から資金を配った**専用 payout 口座**を用意し、鍵を分離:
- `PLAY_PAYOUT`（Play の engagement settle 用）
- `DASH_PAYOUT`（dashboard の faucet/lane earn/node emission 用）
- AD は各campaignのエスクロー残高（実体はtreasury保持でも、送金鍵は`DASH_PAYOUT`で可）
各口座は独立 nonce ストリーム＝プロセス跨ぎでも衝突しない。各口座を定期的に treasury から補充（残高監視）。
※当面「1本の payout 口座＋全 payout を1プロセスに集約」でも可だが、Play settle は在Play・node/ad settle は在dashboard なので**鍵分離が最小変更で確実**。

### (2) 単位系 base=1e6 は「後回し」にする
`MORM_BASE_UNITS_PER_MORM=1e6` は**既存オンチェーン残高を再解釈**する協調マイグレーション（§G）。**初回ローンチは base=1（1 unit=1 MORM）のまま**行う:
- 比例配分/バルブ/AD/node は base=1 で**整数MORM**として正しく動く（検証済みロジックは base に依存しない）。
- view_by_other 等の 1MORM未満のシェアは、`_settle_proportional` が **share<1 を繰越**（settled=0のまま次エポックへ累積）＝**取りこぼし無し・着金が遅れるだけ**。
- sub-MORM 粒度が要るほどの流量になってから §G を実施。→ **初回の risky migration を回避**。

---

## Phase A — 不活性コードを本番へ（挙動ゼロ変化）
1. **dashboard**: フラグ未設定のまま git push → Vercel deploy。
   - 確認: `GET /api/lane/skill`→200／既存 `/api/wallet/*`・`/api/rewards` 不変／`/api/admin/emit-nodes`・`/api/ads/*` は admin/署名ゲートで待機。
2. **play**: play_server.py 転送 → `launchctl kickstart -k gui/$UID/com.morm.play`。
   - 確認: play.morm.one 表示／既存 like/comment/watch/settle(fixed) 不変（`EMISSION_MODE`未設定=fixed, `VIEW_EARN`未設定=off）。
3. **セキュリティ前提（この段で必須）**:
   - `ADMIN_PASSWORD` を**強力な値に設定**（既定`1234`のまま admin 経路[emit-nodes/ad-campaign]を有効化しない）。
   - play plist の `ADMIN_TOKEN` 平文コミットを**ローテ**（既知の課題）。
   - `PLAY_PAYOUT`/`DASH_PAYOUT` 鍵を生成し treasury から初期補充（前提(1)）。dashboard `MORM_TREASURY_SEED/ADDRESS` を `DASH_PAYOUT` に、Play `TREASURY_SEED_FILE` を `PLAY_PAYOUT` に向ける。
- **ロールバック**: 直前 git SHA を Vercel 再デプロイ／旧 play_server.py で再起動。

## Phase B — Agent Lane 稼働（追加的・低リスク）
- `/api/lane/*` は新規追加なので「使えば稼働」。本番 did:key で1周スモーク: register→publish→feed→me→earn。
- `earn` は実 payout。**小さく開始**: `MORM_LANE_EARN=1`（=1 MORM）＋（将来）日次/acct上限。monitor: `lane_earn`・payout 成否。
- **ロールバック**: lane ルートへのトラフィックを止める / `MORM_LANE_EARN`を0扱いに（=earn無効化したいなら route側で0ガード追加）。

## Phase C — 換金バルブ ON（保護・**早期に**）
価格保護は**発行を増やす前に**入れる。
- `BRIDGE_VALVE=on`／`BRIDGE_SYSTEM_DAILY_FRAC=0.005`（0.5%/日・ユーザー確定値）／`BRIDGE_ACCT_DAILY_USD`=保守値／`BRIDGE_COOLDOWN_SEC`=86400。
- 確認: 小額 burn 成功→即再burn 429(cooldown)→上限超 429(system)。price=`/api/price` 実値連動。
- **ロールバック**: `BRIDGE_VALVE` を unset（=off）。

## Phase D — 比例配分 ON（engagement）
- Play `EMISSION_MODE=proportional`＋`B_EPOCH_MORM`（**小さく開始**・日次予算相当）＋`EPOCH_ACCT_CAP_FRAC=0.005`。base=1。
- monitor: `point_settle_runs`（総発行=B で頭打ちを確認）。従来の固定レート settle は置換される。
- `VIEW_EARN=on`＋`PT_VIEW`: **依存**=Play フロントが**署名付き watch ビーコン**を送るクライアント改修が要る（未署名は従来通りview計数のみ）。改修前は view 報酬は発生しない（＝安全な既定）。
- **ロールバック**: `EMISSION_MODE` を fixed に戻す／`VIEW_EARN` off。

## Phase E — ノード比例配分 【❌ 廃止・活性化しない（2026-08-29上書き）】
> **この Phase は撤回。** ノード報酬は node.morm.one の earned が正で、emit-nodes を活性化すると二重支払い/旧DB空配布になる。冒頭「★★2026-08-29確定更新」を参照。以下は歴史的記録として残置（実行しないこと）。
- cron 等で `POST /api/admin/emit-nodes {password,epochLabel}` を定期実行（`SPLIT_NODE`）。`epochLabel` は期間キー（冪等）。
- 既存 `/api/rewards`（週次 fixed snapshot）を**併走 or 退役**を決定（二重払い防止＝どちらか一方に統一）。
- monitor: `node_emissions`。**ロールバック**: cron 停止（新規払いが止まるだけ・既払いは冪等）。

## Phase F — AD エスクロー稼働（収益・発行外）
- 初回広告主: `ad-campaign {action:fund}`（入金tx記録）→配信ノードが `/api/ads/event` に署名累積→`{action:settle}` で CPM 分配。`AD_UNIT_PER_WEIGHT`/`AD_CLICK_WEIGHT` を運用値に。
- monitor: `ad_campaigns.spent≤funded`（発行外の保証）。**ロールバック**: settle 停止。

## Phase G（後日・任意）— base=1e6 sub-MORM 移行【協調マイグレーション】
- 目的: 1MORM未満の細粒度報酬を即時化。
- 手順（要専用runbook）: ①L1の全口座残高を×1e6にrescale（treasury一括 or L1 state migration・**要L1側対応**）②`MORM_BASE_UNITS_PER_MORM=1e6` を dashboard と Play で**同時に**設定 ③`B_EPOCH_MORM`/`AD_UNIT_PER_WEIGHT`/`MORM_LANE_EARN` 等の**単位前提を再校正**（表示は MORM 一定でも内部 units は×1e6）④wMORM/USDブリッジのスケール(1 MORM=1e18 wMORM)との整合を再確認。
- **silent切替禁止**。ロールバックは容易でない（残高を再々スケール要）→ 流量が正当化してから。

---

## 監視・アラート（全Phase横断）
- **treasury/payout 残高の減少レート**（異常な流出＝バグ/farm検知）。各 payout 口座の残高下限アラート＋自動補充。
- `point_settle_runs`/`node_emissions`/`ad_payouts`/`lane_earn`/`bridge_burn_log` の件数・失敗率。
- price oracle 生死（`/api/price` の source が fallback 継続＝バルブが保守cap動作）。
- 決済失敗（`status='failed'`）の再試行キュー。

## 安全チェックリスト（デプロイ承認前）
- [ ] `ADMIN_PASSWORD` 強化・`ADMIN_TOKEN` ローテ済み
- [ ] `PLAY_PAYOUT`/`DASH_PAYOUT` 鍵分離＋初期補充＋残高監視（前提(1)）
- [ ] base=1 で初回（前提(2)）
- [ ] `/api/rewards` と node emission の二重払い方針を確定（Phase E）
- [ ] `B_EPOCH_MORM`・`SPLIT_*`・`MORM_LANE_EARN`・`AD_UNIT_PER_WEIGHT`・バルブ acct上限/cooldown の**初期運用値**を確定
- [ ] Play フロントの署名付き watch ビーコン改修（Phase D の view_earn 前提）

## 推奨順序（まとめ）
A(不活性+鍵分離+admin強化) → **C(バルブ先行)** → B(lane小さく) → D(比例配分+view) → E(node) → F(AD) → 〔後日〕G(base=1e6)。
各段はフラグで即ロールバック。まず A と C を最優先（コードを出し、価格保護を効かせる）。

---

## 21. 初期運用値・鍵配線・補充（デプロイ準備 済 2026-08-26）
デプロイ承認前チェックリストの 1〜3 に対応する準備物:

### 初期運用値（env テンプレート）
- dashboard: [`deploy/env.dashboard.example`](./deploy/env.dashboard.example)
- play: [`deploy/env.play.example`](./deploy/env.play.example)
- 要点（base=1 初回）: `B_EPOCH_MORM=1000`／`SPLIT_ENGAGE=0.60`(Play)＋`SPLIT_NODE=0.30`(dashboard)＝合計0.90(reserve0.10)／`EPOCH_ACCT_CAP_FRAC=0.005`／`MORM_LANE_EARN=1`／バルブ `0.5%日/acct$2/24h`／AD `rate1・click20`。
- **split契約の修正済**: Play `_settle_proportional` に `SPLIT_ENGAGE`(既定1.0=後方互換) を追加。本番で 0.60 にし、node 0.30 と足して発行が B を超えないようにする（従来は Play が B 全額＋node が別枠で 1.3B になっていた不整合を解消）。

### 鍵分離（前提(1)）— 生成済み
| 用途 | address | seed(0600・リポジトリ外) |
|---|---|---|
| PLAY_PAYOUT | `m0r3pos24vwa5d3lq5vqaij75wo3tmyrv4t` | `~/.morm-agentlane/play_payout.seed` |
| DASH_PAYOUT | `m0roshqbpskljwuj3drophhb7tth33qprzn` | `~/.morm-agentlane/dash_payout.seed` |
- Play `TREASURY_SEED_FILE`→PLAY_PAYOUT、dashboard `MORM_TREASURY_SEED/ADDRESS`→DASH_PAYOUT。producer(ブロック生成)は従来 producer.seed のまま。3鍵独立でプロセス跨ぎ nonce 衝突なし。
- 補充手順: [`deploy/fund-payouts.md`](./deploy/fund-payouts.md)（treasury→各口座 kind6・着金確認つき）。★本番 L1 操作＝デプロイ時にユーザー実行。

### Play フロント 署名 watch（Phase D 前提）— 実装＆互換検証 済
- `index.html beaconWatch` を改修: ウォレット有・非unload時=**署名付き watch**(kind=watch, payload={id,watched(整数秒),completed}) を送信＝view_by_other 報酬対象。unload時(pagehide/visibilitychange)=同期・未署名(view計数の信頼性維持)。`uid()==署名者m0r` なので (cid,viewer) dedup で二重計上なし。
- **クロス言語互換を実測確認**: `verify/phase2_signedwatch_sign.mjs`(index.html と同一 canon+Ed25519 で署名) → `phase2_signedwatch_verify.py`(play_server.verify_signed) が **署名検証成功・recovered m0r==署名者**。→ 署名 watch はプロドで確実に earn する。

---

## 22. 残りチェックリスト 確定（2026-08-26）

### (A) /api/rewards 退役方針 — 【⚠️ 2026-08-29 上書き】
> **「ノード報酬を emit-nodes に一本化」は撤回。** ノード報酬の正は node.morm.one の earned（`morm-distribute`→`morm-payout.py`）。emit-nodes/⑤は退役。冒頭「★★2026-08-29確定更新」参照。以下は初版の分析記録（emit-nodesへの一本化方針は無効）。
レガシー・ノード報酬の**実支払い経路**を精査した結果:
- `/api/rewards`(POST) = weekly_snapshots を作るだけの **staging（無支払い）**。
- **実支払いは `/api/admin/send`**（手動で recipients+amounts を渡し `transferMorm` で kind6 送金・snapshot に tx_hash 記録）。
- `/api/my/claim` の merkle 経路（`morm-l1/reward-data/*.json`）は**生成器が存在せず未使用**。
- `nodes.morm_pending/morm_balance` は `completeTaskSuccess` が更新する**表示カウンタ**で、独立に支払う経路は無い。

**方針＝「ノード報酬の支払いは cutover 以降 `emit-nodes` に一本化」**:
- Phase E 以降、**ノードスコアに対する支払いは `POST /api/admin/emit-nodes` のみ**行う。レガシーの `/api/rewards`→`/api/admin/send`（ノード報酬用途）は**使わない**（＝運用停止）。
- **ルートは削除しない**（非破壊）。`/api/admin/send` は汎用の手動送金として温存（ノード報酬以外の臨時送金に使用可）。`/api/rewards`/`/api/my/rewards` は履歴表示として残す。
- **二重払い防止**は運用規律（1期間=1 payer）。emit-nodes は `epochLabel` 冪等、レガシーは week_label と別キーなので**自動ガードは無い**→ 運用手順で「ノード報酬＝emit-nodes のみ」を明記。管理UIの週次送信ボタンはノード報酬に使わない。

### (B) 初期運用値 — 最終GO（base=1・少人数ローンチ）
| パラメータ | 値 | 根拠 |
|---|---|---|
| `MORM_BASE_UNITS_PER_MORM` | **1** | 初回は base=1（sub-MORM §G は後日） |
| `B_EPOCH_MORM` | **1000** /エポック | $0.0136で名目$13.6/日。換金は0.5%pool≈$5.8/日で律速。低volume早期に十分 |
| `SPLIT_ENGAGE`(Play) / `SPLIT_NODE`(dash) | **0.60 / 0.30** | 合計0.90(reserve0.10)。発行が B を超えない |
| `EPOCH_ACCT_CAP_FRAC` | **1.0**（早期）→将来 0.05→0.005 | ★少人数では集中が自然。cap 0.005 だと予算が出ず starve。網拡大＋untrusted流入で絞る |
| `MORM_LANE_EARN` / `MORM_LANE_EARN_DAILY_CAP` | **1 / 10** | ★lane earn は ref実在検証なし＝farmable。小さく＋日次上限で絞る。実 earning は budget上限トラック(view/node/AD)が担う。0で無効化も可 |
| バルブ `SYSTEM_DAILY_FRAC/ACCT_DAILY_USD/COOLDOWN/FALLBACK` | **0.005 / 2 / 86400 / 3** | 価格保護優先（ユーザー確定 0.5%/日） |
| AD `UNIT_PER_WEIGHT / CLICK_WEIGHT` | **1 / 20** | base=1 の下限。§G後に細粒度化 |

**GO判定**: 上記で初回ローンチ可。数値はすべて env で即調整でき、budget系は総発行が B に頭打ち＝暴走しない。lane earn だけ非budget系なので日次上限で封じた。

### 追加ハードニング（この確定で実施済）
- **lane earn 日次上限**を実装（`app/api/lane/earn`: `MORM_LANE_EARN_DAILY_CAP`・0で403無効化・24h件数で429）。

### チェックリスト最終状態
- [x] `PLAY_PAYOUT`/`DASH_PAYOUT` 鍵分離＋補充runbook（§21）
- [x] base=1 初回（前提(2)）
- [x] `/api/rewards` 退役方針（＝emit-nodes 一本化・上記A）
- [x] 初期運用値 確定（上記B）
- [x] Play 署名 watch 改修＋互換検証（§21）
- [ ] `ADMIN_PASSWORD` 強化・`ADMIN_TOKEN` ローテ（★デプロイ実作業時にユーザー実施）
- [ ] payout 口座の初期補充（★デプロイ実作業時にユーザー実施＝L1操作）
→ 残りはコードでなく**デプロイ当日のユーザー実作業**のみ。設計・準備は完了。
