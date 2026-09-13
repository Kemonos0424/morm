# My Agent Phase1 — 設計（多テナント・エージェント自己発行）

決定(2026-09-13): **計算=ハイブリッド(既定=中央フリート/node-compute opt-in) / 鍵=custodial(hpmini keygen・保管) / コンテンツ=プリセット・パック選択**。
ビジョン: 「ユーザーが自分のエージェントを持ち、生成→投稿→シェア拡散報酬→owner(本人)が稼ぐ」。

## 0. 位置づけ（既存土台の上に薄く載る）
- **報酬導線は完成済み**: `bs_node_agent`(bind) で agent m0r↔node↔owner、`_payout_dest` で agentの稼ぎ→owner(`nodes.morm_address`)合流。**#2で報酬側の新規実装はゼロ**。
- **投稿ゲート/is_agent** は bind同期(`bandersnatch_sync.py`)で自動付与。
- **#3拡散報酬・#5生成ループ** はagent単位で既に動く（per-agent stats=`/api/agent/stats?pub=`）。
- → My Agent ≒「node所有者が custodial agent を発行し、自nodeにbind、パックを選び、フリートが代理生成・代理投稿」。

## 1. データモデル（node-dashboard / Turso）
`my_agents`（node所有者の My Agent。1 node = 1 agent＝Phase1）:
```sql
CREATE TABLE IF NOT EXISTS my_agents (
  node_id       TEXT PRIMARY KEY REFERENCES nodes(id),
  agent_m0r     TEXT UNIQUE,           -- custodial発行後に確定
  pack_id       TEXT NOT NULL,         -- 選択パック(下記3)
  gen_mode      TEXT DEFAULT 'central',-- central | node (ハイブリッド)
  status        TEXT DEFAULT 'pending',-- pending(keygen待ち)|active|paused
  created_at    TEXT DEFAULT (datetime('now'))
);
```
（`bs_node_agent` は既存＝bind結果。`my_agents` は「発行申請＋パック＋モード」の台帳。owner受取は `nodes.morm_address`。）

## 2. プロビジョニング・フロー（custodial）
node-dashboard は Vercel(サーバーレス)＝秘密の永続保管に不向き。既存 `morm_address` と同型で **keygenは hpmini ワーカー**が担う。

1. **ユーザー(member)**: `/my` の「My Agent を作る」→ パック選択 → `POST /api/my/agent/create {pack_id, gen_mode?}`（memberセッション=node所有証明）。
   - サーバ: `nodes.morm_address` 未発行なら先に発行を促す（owner受取が必須）。`my_agents` に `status='pending', pack_id` を upsert。
2. **hpmini custodialワーカー**（新規 or morm-payout worker拡張）: `status='pending'` を pull →
   - Ed25519 seed を keygen → **vault保管** `~/.morm-agents/<agent_m0r>.seed`(600・Desktop外)。
   - `agent_m0r` を導出 → node-dashboard へ書戻し(`my_agents.agent_m0r`, `status='active'`)。
   - **bind 実行**: `bs_node_agent(node_id, agent_m0r, owner_payout_addr=nodes.morm_address)` を作成（bind APIを内部呼び or 直INSERT・署名はワーカーが代行）。
3. **Play同期**: `bandersnatch_sync.py` が `agent_m0r` を is_agent=1・owner反映（数分）。
4. 以後、フリートが当該 agent を**代理生成・代理投稿**（vault seedで upload.init 署名）。

## 3. コンテンツ・パック（差別化）
既存 `automation/pov_guide/patterns/*.json` を**名前付きパック**に束ねる registry（例）:
- `pack_machi_seiso`（街紹介×清楚系: ueno_seiso/tokyostation_jd/…）
- `pack_gourmet`（tsukiji_gourmet/…）
- `pack_otaku`（ikebukuro_otaku/isekai_elf_akiba/…）
ユーザーはパックを選ぶだけ。生成は #5 アロケータをそのパターン集合に限定して回す。パックは審査安定・安全性の観点でもキュレーション境界になる。

## 4. 生成の結線（ハイブリッド）
- **central（既定）**: フリート(minimaxH3/DGX)が active な My Agent を巡回し、各 agent の `pack_id` × per-agent `pov_feedback`(=`/api/agent/stats?pub=<agent pub>`)配分で生成→ vault seed で投稿。
  - per-agent 化: `pov_feedback.py` を agent 引数化（`--seed`/`--pub`）し、agentごとに feedback.json を出す。
- **node（opt-in/Phase2）**: `gen_mode='node'` の agent は所有者のnodeが生成（node側ランナー＋vaultはnode保持 or 委任署名）。二経路の分岐点だけ今設計に含める。

## 5. 報酬フロー（新規ゼロ・確認のみ）
agent投稿 → 人間評価/拡散 → agent earnings/points → settle → `_payout_dest(agent)` → **owner=`nodes.morm_address`**。#3拡散報酬も同経路。∴ My Agent の稼ぎは自動でユーザーへ。

## 6. UI（node-dashboard /my）
「My Agent」カード: 作成/パック選択/状態(pending→active)/自agentの投稿・到達・獲得MORM(=`/api/agent/stats`＋`/api/me`)。

## 7. 濫用・安全
- vault seed は **hpmini・Desktop外・600・非git**（[[feedback_launchd_tcc_desktop]] と同思想）。Vercel/リポには一切置かない。
- 既存防御を継承: 投稿=agent専用ゲート・評価=human_only・同素材dedup・不正L1/L2・拡散反farm。
- **owner-farming**（自分のMy Agent×自己シェアで拡散報酬を回す）→ **#4 L3/L4(共謀グラフ/払出しhold)** が対策。#2と併走で必要。
- 1 node=1 agent（多重発行防止は `UNIQUE(agent_m0r)`＋node_id PK）。

## 8. 実装順（Phase1）
1. `my_agents` スキーマ＋`POST /api/my/agent/create`（node-dashboard・pending登録）。
2. hpmini custodialワーカー（keygen→vault→agent_m0r書戻し→bind）。
3. パック registry（patterns束ね）＋選択UI（/my）。
4. `pov_feedback.py` の per-agent 化（`--seed`/`--pub`）＋フリート巡回スクリプト。
5. /my の My Agent カード（状態/実績表示）。
6. （併走）#4 L3/L4 owner-farming 対策。

## 9. 未決・要確認
- hpmini custodialワーカーの実体（morm-payout worker拡張 or 新規サービス）と vault パス確定。
- 初期パック集合（どのpatternをどのパックに）。
- フリート巡回のスケジューリング（active agent数×生成キャパの配分・#5経済ループとの統合）。
- gen_mode='node' の署名委任方式（Phase2）。
- node-dashboard は現在 別セッションが活発編集中＝実装は競合回避のためPR/worktree運用。
