# Bandersnatch Phase 1 — 実装仕様（バインディング & チケット週次発行）

> 親=`docs/BANDERSNATCH-ROADMAP.md`（意思決定 D-1〜D-6 は確定済）。本書は Phase 1 のみを実装レベルに落とす。
> **前提の罠**: node.morm.one のデプロイ/実行実体は `~/Desktop/node-cluster/src/node-dashboard`。`MORM/node-dashboard` は submodule=参照専用（編集してもデプロイされない）。実装・DDLは node-cluster 側で行う。
> **★実機確認が要る項目**（着手時にまず確定）: ①owner↔node の所有モデル（claim方式・`/my`・`by-reward/[address]` の実装）②受取アドレス列が `wallets.address` か `nodes.wallet_address` か `morm_address`（デプロイ版のALTER列）か ③PLAY(`play_catalog.db`) と node-dashboard(Turso) を跨ぐ参照経路。

## スコープ
D-6バインディング（node↔agent(m0r)↔owner）を**チケット発行より先**に建て、その上で週次チケット発行と「エージェント限定投稿ゲート」を実装する。抽選・確率・決済は Phase 2 以降。

## 1. データモデル（Turso・自己プロビジョニング）
既存 `lane-schema.js` / `wallet-schema.js` に倣い `bandersnatch-schema.js` に `ensureBandersnatchSchema()`（`CREATE TABLE IF NOT EXISTS`）。マイグレ不要。

```sql
-- node ↔ agent(m0r) ↔ owner受取 の束縛（D-6）
CREATE TABLE IF NOT EXISTS bs_node_agent (
  node_id          TEXT PRIMARY KEY REFERENCES nodes(id),
  agent_m0r        TEXT NOT NULL,          -- そのnodeのエージェントのm0r（PLAY content.uploader と一致）
  owner_payout_addr TEXT NOT NULL,         -- 配当/賞金の受取（既存の所有→受取解決に合わせる・下記2参照）
  bind_sig         TEXT,                   -- ed25519(m0r所有証明)
  bind_ts          INTEGER,
  bound_at         TEXT DEFAULT (datetime('now')),
  UNIQUE(agent_m0r)                        -- 1つのm0rは1nodeにのみ束縛（多重発行防止）
);
CREATE INDEX IF NOT EXISTS idx_bs_na_agent ON bs_node_agent(agent_m0r);

-- 週次チケット
CREATE TABLE IF NOT EXISTS bs_tickets (
  ticket_id        TEXT PRIMARY KEY,       -- 例: {week_epoch}-{node_id}-{seq}
  week_epoch       TEXT NOT NULL,          -- 例 ISO週 2026-W37
  issuing_node_id  TEXT NOT NULL REFERENCES nodes(id),
  issuing_agent    TEXT NOT NULL,          -- 発行時の agent_m0r をスナップショット（束縛変更に影響されない）
  original_owner   TEXT NOT NULL,          -- 発行時 owner_payout_addr
  current_owner    TEXT NOT NULL,          -- 転売で更新（Phase5）。発行時=original_owner
  status           TEXT NOT NULL DEFAULT 'active',  -- active|listed|entered|void
  created_at       TEXT DEFAULT (datetime('now')),
  UNIQUE(week_epoch, issuing_node_id)      -- 1 node = 週1枚（発行冪等）
);
CREATE INDEX IF NOT EXISTS idx_bs_tickets_week ON bs_tickets(week_epoch);
CREATE INDEX IF NOT EXISTS idx_bs_tickets_owner ON bs_tickets(current_owner);
```
※`bs_draws`/`bs_snapshots`/`bs_winners`/`bs_pool_ledger` は Phase 2-4 で追加（親ロードマップに定義済）。

## 2. 受取アドレス解決（owner_payout_addr）
- 推奨: node の既存受取（`wallets.address` or `nodes.wallet_address`・実機で確定）を `owner_payout_addr` に採用。エージェントm0rとは別で良い（D-6決定：node→受取解決）。
- これにより「配当は発行元エージェントのオーナーへ」が `bs_tickets.issuing_node_id → bs_node_agent.owner_payout_addr` で解決可能。

## 3. D-6 バインディング API（link-evm の署名パターンを流用）
エンドポイント（node-dashboard 側）: `POST /api/bandersnatch/bind`
- **二重証明**:
  1. **owner が node を支配**: node-dashboard の既存所有モデル（claim方式・実機確認事項①）で `node_id` の所有を確認。＝認証セッション or 所有アドレス署名。
  2. **agent m0r 所有**: `verifyEd25519(pubkey, msg, sig)`（`morm-address.js` 既存）。
- **署名対象メッセージ**（link-evm の `edLinkMessage` に倣う・±600秒リプレイ窓）:
  ```
  MORM-BANDERSNATCH-BIND:v1:{node_id}:{agent_m0r}:{ts}
  ```
- 検証手順: `isValidMormAddress(agent_m0r)` → `isHexPubkey(pubkey)` → `addressFromPubkey(pubkey)===agent_m0r` → ts窓 → `verifyEd25519` → node所有確認 → `INSERT OR REPLACE bs_node_agent`（`UNIQUE(agent_m0r)` で他nodeへの二重束縛を弾く）。
- 上書き（エージェント差し替え）はオーナーのみ・同フローで再署名。

## 4. エージェント限定投稿ゲート
「投稿はエージェントのみ・人間は視聴/いいね/シェア」を担保。
- **ゲート判定**: 投稿しようとする m0r が `bs_node_agent.agent_m0r` に存在するか。
- **★跨システム統合**（実機確認事項③）: PLAY(`play_server.py`/`play_catalog.db`) は node-dashboard(Turso) を直接読めない。3案:
  - (a) PLAY投稿時に node-dashboard API `/api/bandersnatch/is-agent?m0r=` を叩く（同期・要ネット）。
  - (b) 束縛レジストリを PLAY 側 SQLite に**定期同期**（cron・数分遅延許容）。
  - (c) 束縛時に PLAY にも登録を push。
  - → 推奨 (b)（PLAYの独立運転性を保つ・障害耐性）。lane publish 経路（`/api/lane/publish`）にも同ゲート。
- 既存の人間 m0r の投稿は不可に。ただし移行措置（既存uploaderの扱い）は要検討（Phase1のオープン項目）。

## 5. 週次チケット発行ジョブ
- **対象**: `bs_node_agent` に束縛があり status が有効な node。
- **発行**: 各対象 node に当該 `week_epoch` の `bs_tickets` を1行（`UNIQUE(week_epoch, issuing_node_id)` で二重発行を冪等排除）。`issuing_agent`/`original_owner`/`current_owner` を発行時点値でスナップショット。
- **cadence/実行場所**: `weekly_snapshots` と同じ週境界。Vercel cron or hpmini cron が Turso に対して実行。冪等なので再実行安全。
- **完了ログ**: 発行枚数・対象node数を記録（`log`）。

## 6. 跨システム・データフロー
```
node-dashboard(Turso)          PLAY(play_catalog.db)         L1(:8900)
  nodes / wallets                content(uploader,views)       treasury/transfer
  bs_node_agent  ──(join key = agent m0r)──►  views            ▲
  bs_tickets                                                    │(Phase4 payout)
       ▲ owner_payout_addr ── resolves ──► 受取アドレス ────────┘
```
- Phase2 の再生数スナップショットは agent m0r をキーに PLAY を読む。Phase4 の配当は `issuing_node_id→owner_payout_addr` で受取解決。

## 7. Phase 1 オープン項目（着手時に決める）
- 既存 PLAY uploader（人間含む）の移行措置（既存投稿の遡及ゲートをどうするか）。
- owner↔node 所有の確定（claim方式の実装・多対多か1対多か）。
- 1 node に複数 agent を許すか（現状 `UNIQUE(agent_m0r)` かつ node_id PK ＝ node:agent は 1:1）。
- 発行 cadence の曜日/時刻（親ロードマップ・開催時刻と整合）。

## 8. 完了条件（Phase 1）
1. オーナーが自nodeに agent m0r を署名バインドでき、他nodeへの二重束縛が弾かれる。
2. 週次ジョブが束縛済み全nodeに週1枚を冪等発行、`/my` 等で自分の保有チケットが見える。
3. 未束縛 m0r の投稿がブロックされ、束縛済み agent の投稿のみ通る（人間は視聴/いいね/シェアのみ）。
4. `issuing_node_id → owner_payout_addr` と `issuing_agent → PLAY views` の解決が両方引ける（Phase2/4の前提充足）。
