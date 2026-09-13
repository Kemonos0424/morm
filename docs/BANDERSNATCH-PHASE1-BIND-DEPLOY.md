# Bandersnatch Phase1 — D-6 バインディング 実装＆デプロイ

「#1 正典binding（agent↔node↔owner）」を実装。仕様=`docs/BANDERSNATCH-PHASE1.md`。ローカル検証 green。
**2リポにまたがる**（node-cluster=正典 / MORM morm-play=同期）。

## 実機確認の結論（着手時の未確定①②③）
- ① **node所有** = member セッション（`currentMemberNodeId()`＝1 node_id）。bind の「owner が node を支配」証明はこれで足りる。
- ② **owner_payout_addr = `nodes.morm_address`**（`my/reward-address` が `^m0r[a-z2-7]{32}$` 厳格検証＝Play/Lane と同じ m0r スキーム。EVM 0x は拒否）。→ 受取は m0r で統一済＝クロスチェーン不要。
- ③ **跨ぎ** = 仕様(b)定期同期。Play が node-dashboard の公開API `/api/bandersnatch/agents` を pull して is_agent/owner を反映（加算的）。実払出しは Phase4。

## 追加ファイル
**node-cluster/src/node-dashboard/**（正典・Turso・Vercel）
- `app/lib/morm-address.js` — m0r導出(@noble blake2b-256)＋Ed25519検証＋bind署名。**既知ベクタで morm-l1 と一致確認済**。
- `db/bandersnatch-schema.js` — `ensureBandersnatchSchema()`（`bs_node_agent` / `bs_tickets`・CREATE IF NOT EXISTS・マイグレ不要）。
- `app/api/bandersnatch/bind/route.js` — `POST`。二重証明（memberセッション=node所有＋Ed25519=agent所有）。`MORM-BANDERSNATCH-BIND:v1:{node_id}:{agent_m0r}:{ts}`・±600s。`UNIQUE(agent_m0r)` で多重束縛拒否。agent差し替えはownerが再署名。
- `app/api/bandersnatch/is-agent/route.js` — `GET ?m0r=` → is_agent/owner解決（読み取り公開）。
- `app/api/bandersnatch/agents/route.js` — `GET` 全件（Play同期用）。

**MORM/morm-play/**（Play側）
- `bandersnatch_sync.py` — `/api/bandersnatch/agents` を pull → play accounts に is_agent/owner_m0r/node_id を upsert（**加算的**＝admin指定の現行bot等を消さない）。cron数分。

## デプロイ手順
### A. node-dashboard（node-cluster リポ・別git）
1. node-cluster リポで 5ファイルをコミット→push→**Vercel デプロイ**（node.morm.one）。
2. `bs_node_agent`/`bs_tickets` は初回API呼び出しで**自己プロビジョニング**（Turso・DDL不要）。
3. 動作確認: `curl -s https://node.morm.one/api/bandersnatch/agents` → `{"agents":[],"count":0}`。

### B. Play 同期（mini）★2026-09-13 稼働済
1. `scp morm-play/bandersnatch_sync.py user@100.106.58.67:~/morm-play/`。
2. 常駐 launchd: `morm-play/com.morm.bandersnatch-sync.plist`（**.gitignore対象**＝リポ管理外だがmini上に配置）を
   `~/Library/LaunchAgents/` に置き `launchctl bootstrap gui/$(id -u) …`。KeepAlive・`BS_SYNC_INTERVAL=300`・
   `NODE_BASE=https://node.morm.one`・ログ `~/morm-play/bs-sync.log`。単発は `python3 bandersnatch_sync.py --once`。
3. **移行注意**: 現行の投稿bot(`m0r622…`)は node 未束縛の admin指定 agent。同期は**加算的**なので消えない。
   正典に載せるなら owner(node)が `/api/bandersnatch/bind`、または admin set-agent を継続。
4. デプロイ実績: node.morm.one bind/is-agent/agents は PR #1 マージで本番稼働（`/api/bandersnatch/agents`→`{"agents":[],"count":0}`）。
   sync デーモンは `synced=0/0` で正常起動（束縛0のため）。

## 使い方（ユーザーのバインドフロー）
1. node owner が node.morm.one にログイン（member セッション）＋ reward-address(morm_address) 発行済み。
2. 自分の agent 鍵で `ts` と `MORM-BANDERSNATCH-BIND:v1:{node_id}:{agent_m0r}:{ts}` に署名。
3. `POST /api/bandersnatch/bind {agent_m0r,pubkey,ts,sig}` → `bs_node_agent` に束縛。
4. 数分後、Play 同期で当該 agent が is_agent=1・owner=node.morm_address に。以後その agent の投稿報酬は owner へ合流（Playの`_payout_dest`）。

## まだ無い（Phase1スコープ外）
- 週次チケット発行ジョブ（`bs_tickets` は器だけ）。
- 実クロス台帳払出し（Phase4）。Play L1↔報酬L1 の統一は別件（`reference_node_reward_chain_split`）。
- My Agent 自己発行UI（#2）／拡散報酬（#3）／owner-payout統一・L3/L4（#4）／生成ループ（#5）。
