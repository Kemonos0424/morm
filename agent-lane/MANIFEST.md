# Agent Lane — 改変・追加ファイル一覧（レビュー / デプロイ用）

すべて**非破壊**。新機能は環境変数フラグで gate し、既定値は現行挙動。デプロイしてもフラグを立てるまで挙動は不変。

## morm-dashboard（Vercel / api.morm.one）

### 追加（新規ファイル）
| ファイル | 目的 |
|---|---|
| `app/lib/morm-units.js` | 単位系の単一真実源（MORM↔base units・`baseUnitsPerMorm/mormToUnits/unitsToMorm/formatMorm`） |
| `app/lib/lane-schema.js` | エージェントレーンの `lane_content` / `lane_earn`（自己プロビジョン） |
| `app/lib/morm-price.js` | 価格+USDC準備金リーダ（Uniswap slot0・env override可・本番/api/price非改変） |
| `app/lib/bridge-valve.js` | 換金バルブ（`bridge_burn_log`＋`checkBurn`/`recordBurn`） |
| `app/lib/node-emission.js` | ノード比例配分（`planNodeEmission`/`settleNodesProportional`・`node_emissions`冪等） |
| `app/lib/ad-escrow.js` | ADエスクロー（`ad_campaigns/ad_events/ad_payouts`・fund/recordAdEvent/settleCampaign・**発行外の予算上限再分配**） |
| `app/api/ads/event/route.js` | 署名付きADイベント(impression/click)累積（dedup） |
| `app/api/admin/ad-campaign/route.js` | ADキャンペーン管理 fund/settle/status（`ADMIN_PASSWORD`ゲート） |
| `app/api/lane/skill/route.js` | fetch-only エージェント向けオンボーディング（md） |
| `app/api/lane/publish/route.js` | agent署名 REGISTER_CONTENT(kind1) 中継＋feed索引 |
| `app/api/lane/feed/route.js` | 新着コンテンツJSON（公開読み） |
| `app/api/lane/me/route.js` | 実L1残高/nonce/stake＋lane実績（`balanceMorm`付き） |
| `app/api/lane/earn/route.js` | 署名クレーム→dedup→treasury kind6 payout |
| `app/api/admin/emit-nodes/route.js` | ノード比例配分の管理トリガ（`ADMIN_PASSWORD`ゲート） |

### 変更（既存ファイル）
| ファイル | 変更点 |
|---|---|
| `app/lib/morm-address.js` | `laneEarnMessage()`＋`adEventMessage()` 追加 |
| `app/lib/morm-l1.js` | `relayTx`/`getContent` 追加、`transferMorm` を**直列化mutex＋着金確認**化（nonce衝突解消） |
| `app/lib/db.js` | ローカルsqliteに `LOCAL_SQLITE_URL` override（既定不変） |
| `app/api/wallet/account/[address]/route.js` | `balanceMorm/stakeMorm/lockedMorm`＋`baseUnitsPerMorm` を加算的に返す |
| `app/api/wallet/bridge-burn/route.js` | 中継前に換金バルブ `checkBurn`、成功後 `recordBurn`（フラグoffでbypass） |

## morm-play（Mac Mini / play.morm.one）

### 変更（`play_server.py`）
| 箇所 | 変更点 |
|---|---|
| 定数 | `POINT_VALUES["view"]`＋`VIEW_EARN`、`EMISSION_MODE`/`MORM_BASE_UNITS_PER_MORM`/`B_EPOCH_MORM`/`EPOCH_ACCT_CAP_FRAC` |
| `settle_points()` | `EMISSION_MODE` 分岐へ。`_settle_fixed()`（従来の逐語移設）＋`_settle_proportional()`＋`_record_settle_run()` |
| `grant_view_point()` | 新規: 他者の有効再生→クリエイターへ視聴ポイント（dedup key=`cid\|viewer`） |
| `record_watch()` | 引数 `viewer_verified` 追加＋新規有効再生で `grant_view_point` 呼び出し |
| `/api/watch` | 署名レーン追加（`verify_signed(data,"watch")`／未署名は従来通りview計数のみ） |

## 有効化フラグ（本番デプロイ後・段階的に）
既定はすべて現行挙動。順序・詳細は `AGENT_LANE_from_FLOP.md` §11/§18/§19。

| フラグ | 既定 | Phase2値 | 対象 |
|---|---|---|---|
| `MORM_BASE_UNITS_PER_MORM` | `1` | `1000000`（★協調マイグレーション要） | 両方 |
| `EMISSION_MODE` | `fixed` | `proportional` | Play |
| `B_EPOCH_MORM` / `EPOCH_ACCT_CAP_FRAC` | 5000 / 0.005 | 運用値 | 両方 |
| `SPLIT_NODE` | 0.30 | 運用値 | dashboard(node) |
| `VIEW_EARN` / `PT_VIEW` | `off` / 1 | `on` / 運用値 | Play |
| `BRIDGE_VALVE` | `off` | `on` | dashboard |
| `BRIDGE_SYSTEM_DAILY_FRAC` | 0.005 | 0.005(=0.5%) | dashboard |
| `BRIDGE_ACCT_DAILY_USD` / `BRIDGE_COOLDOWN_SEC` / `BRIDGE_FALLBACK_DAILY_USD` | 50 / 86400 / 5 | 運用値 | dashboard |
| `AD_UNIT_PER_WEIGHT` / `AD_CLICK_WEIGHT` | 1000 / 20 | 運用値(CPM) | dashboard(ads) |
| `MORM_PRICE_OVERRIDE_USD` / `MORM_RESERVE_USDC_OVERRIDE` | 未設定 | 緊急時のみ | dashboard |
| `LOCAL_SQLITE_URL` | 未設定 | test/dev のみ | dashboard |

`MORM_LANE_EARN_DAILY_CAP`(既定10・0で無効) で lane earn を絞る（ref実在検証が無く farmable のため）。

node emission は cron 等で `POST /api/admin/emit-nodes {password,epochLabel}` を定期実行。
AD は `POST /api/admin/ad-campaign {action:fund}` で広告主入金を記録→配信で `/api/ads/event`(署名) 累積→`{action:settle}` で配信者へCPM分配（予算上限内・発行外）。

## デプロイ前チェック
- `MORM_BASE_UNITS_PER_MORM` の 1→1e6 切替は**既存オンチェーン残高を再解釈**する。rescale か 新エポック運用の協調が要る（silent切替禁止）。
- 換金バルブ有効化時は本番 treasury の実MORMを守るため、まず保守的な `BRIDGE_ACCT_DAILY_USD`/`BRIDGE_COOLDOWN_SEC` から。
- `emit-nodes`/`VIEW_EARN`/proportional settle は本番 treasury を消費。B_EPOCH/split を先に確定。
