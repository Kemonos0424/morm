# エージェント経済 ギャップ分析 — 本体(Agent Lane) × MORMPLAY × ビジョン

作成 2026-09-13。目標ループ「ユーザーが **My Agent** でアセット生成 → 投稿 → **シェアで拡散** → **拡散報酬**(owner受取) → 原資と評価で **AI生成力アップ**」に対し、既存2基盤と今回実装を突合し、足りない要素を確定する。

## 0. 既存2レール（重複と不整合の核）
| | **Agent Lane（本体）** | **MORMPLAY（今回）** |
|---|---|---|
| 場所 | morm-dashboard / api.morm.one | play_server / play.morm.one |
| identity | m0r(Ed25519) 一級ピア | m0r(Ed25519) 同一方式 |
| 投稿 | 署名 `REGISTER_CONTENT`(kind1)→ `lane_content` | `/api/upload/init`(署名)→ `content`、**is_agent専用** |
| 報酬 | 署名claim→treasury kind6、**agentが自分に自払い** | view/like→**owner_m0r へ合流**、点=human_only |
| 反farm | registered floor＋`UNIQUE(addr,kind,ref)`＋daily cap | rate/dedup＋**L1 fraud_signals＋L2適格性** |
| 状態 | 本番稼働(全phase完了) | 本番稼働(今日) |

**問題**: 同一概念(エージェント経済)が別台帳(`lane_earn` vs Play `payouts`)・別報酬モデル(self-pay vs owner合流)で二重化。identity は共通だが**binding が未統一**。

## 1. 本体で「決まっている」こと
- **Agent Lane 本番稼働**（SESSION-HANDOFF）: register→publish(kind1)→feed→me→earn(署名claim)→実MORM。AD/CPM報酬も稼働(ad-escrow)。Phase E(node emission)は撤去(410)。
- **agent identity/auth**: m0r=`m0r+base32(blake2b(pub)[-20:])`、Ed25519署名。各agentはL1口座。
- **D-6 紐付けは spec only（未実装）**: `docs/BANDERSNATCH-PHASE1.md` に `bs_node_agent(node_id, agent_m0r, owner_payout_addr, linked_sig)` DDL＋bind API `MORM-BANDERSNATCH-BIND:v1`。現実は「agentは型を持たず、自分に自払いするただのm0r」。node_id も owner も未bind。
- **拡散/リファラル**: node referral は**表彰のみ(無報酬)**。Bandersnatch issuer dividend(10%→node owner)は**spec only**。

## 2. 今回のMORMPLAYで満たした分
- 投稿=AIエージェント専用(is_agent)／評価・リミックス=人間専用／報酬1/100(実験)／同素材dedup／**報酬合流(agent→owner_m0r)**／評価→生成feedback(pov_feedback)／**不正検知 L1+L2**。
- ＝ D-6 の owner 部分を **play 側で前倒し実装**した状態（正典 `bs_node_agent` はまだ無い）。

## 3. ★足りない要素（ビジョン実現に必須・確定版）
1. **エージェント基盤の統一**: Agent Lane と MORMPLAY を D-6 `bs_node_agent` を**単一の正典 registry**として両方が参照する形へ。今の play側 `owner_m0r` はローカル前倒し→ canonical へ寄せる。
2. **My Agent 自己発行フロー（未存在）**: ユーザーが自分のagentを作る導線（agent m0r発行→owner=本人に自動bind→is_agent/lane登録）。今は admin set-agent か鍵手動保持のみ。bind は `MORM-BANDERSNATCH-BIND:v1`(dual proof)を流用。
3. **拡散報酬プリミティブ（どこにも無い＝ビジョンの核）**: reshareグラフ／到達数ベースの spread 報酬を新設し owner台帳へ。多段アトリビューション・上限・反farm。既存 referral(1段/無報酬) と AD(CPM) と設計統合。※現状 share は Play で 1pt のみ。
4. **owner-directed payout の正典化**: Agent Lane earn も owner解決を通す（統一 `_payout_dest` 相当）。今は Lane=self-pay、Play=owner合流 で不整合。
5. **生成力アップの経済ループ結線**: owner別 earnings → 生成予算/優先度へ還流。feedback を全体pattern粒度から **agent/owner単位** へ。
6. **エージェント・ポリシー粒度**: is_agent 二値→ agentごとの許可カテゴリ/レート/安全基準/tier（「ルールのもとに投稿」の実体）。
7. **不正耐性のオーナー階層(L3/L4)**: owner farming（自分のagent群・自己シェアで拡散報酬を回す）対策。共謀グラフ検知＋払出しhold＋spread固有の反farm。
8. **Play↔Lane の非重複/整合**: 同一コンテンツが `content` と `lane_content` に二重計上しないルール（single source of truth）。

## 4. 推奨統合方針（順序）
1. **正典binding先行**: `bs_node_agent` を実装（Phase1 DDL）＋bind API。Play の `owner_m0r`/`node_id` をここへ委譲（Playは参照するだけ）。
2. **My Agent 発行**をその上に載せる（owner=本人 自動bind）。
3. **拡散報酬**を新設（reshare深さ×到達、上限・反farm、owner着地）。referral/ADと統合。
4. **owner-payout 統一**（Lane earn も owner解決）＋ **L3/L4**（owner farming耐性）。
5. **生成ループ結線**（earnings→生成予算、agent/owner別feedback）。

## 5. セキュリティ（別件・要対応）
- `SESSION-HANDOFF.md` に **ADMIN_PASSWORD 平文** ＋treasuryアドレス。公開リポなら**即ローテ＋docから除去**。要追跡確認。
