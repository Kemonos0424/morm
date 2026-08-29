# MORM Agent Lane

FLOP/Technocore（Arthur Hayes）の構造分析から生まれた、**MORM を「AIエージェント経済 + MORMNODE成果報酬 + MORM Play + AD」を一本の経済レールに載せる**ための取り組み。

- **正典（全設計・数式・検証ログ）**: [`AGENT_LANE_from_FLOP.md`](./AGENT_LANE_from_FLOP.md)
- **本番デプロイ計画（段階ロールアウト・前提・チェックリスト）**: [`DEPLOY.md`](./DEPLOY.md) ／ env テンプレート・補充手順 = [`deploy/`](./deploy/)
- **改変・追加ファイル一覧（レビュー/デプロイ用）**: [`MANIFEST.md`](./MANIFEST.md)
- **実チェーン検証スクリプト**: [`verify/`](./verify/)（`verify/run_all.sh` で一括）
- 関連メモリ: `project-flop-technocore-airdrop` / `project-morm-play-discovery` / `reference-morm-play-l1-integration` / `project-morm-node-hardware`

## 一行で
「価値を出す → 署名1リクエスト → 実MORMが自動着金」を**人間UIを介さず**回せる土台。engagement(視聴/いいね/投稿) と node(端末提供/検証済み仕事) を **同じ予算上限つき比例配分** `Payout_i = B_epoch × Score_i / ΣScore` に載せ、換金は価格保護バルブで律速する。

## 状態（すべて実装＋**実チェーン検証済**・非破壊フラグ/既定）
| # | 内容 | 実体 | 検証 |
|---|---|---|---|
| P0 | エージェントが署名公開→実MORM受領 | L1直 | `verify/phase0_agent_earn.py` |
| P1 | fetch-only エージェントレーン `/api/lane/*` | dashboard | `verify/phase1_run.sh` |
| ① | 単位系統一（sub-MORM, `morm-units.js`） | dashboard | `verify/phase2_units_run.sh` |
| ② | 比例配分エポックバッチ（総発行B固定） | Play `settle_points` | `verify/phase2_prop_run.sh` |
| ③ | 換金バルブ（システム日次0.5%+acct上限+cooldown） | dashboard `bridge-valve` | `verify/phase2_valve_run.sh` |
| ④ | view_by_other（署名付き他者視聴→クリエイター実収益） | Play | `verify/phase2_view_run.sh` |
| ⑤ | MORMNODE報酬を同一B_day比例配分に統合 | dashboard `node-emission` | `verify/phase2_node_run.sh` |
| ⑥ | ADエスクロー三角形（広告主入金→配信/クリエイターへCPM分配・**発行外**） | dashboard `ad-escrow` | `verify/phase2_ads_run.sh` |
| — | `transferMorm` 直列化+着金確認（nonce衝突解消） | dashboard `morm-l1.js` | ⑤で実証 |

**Phase 2 完了**。次: **本番デプロイ計画**（全フラグ既定off＝現行維持。有効化順・`MORM_BASE_UNITS_PER_MORM=1e6` の協調マイグレーション・段階ロールアウト）。

## 安全設計（重要）
- **すべて非破壊**: 新機能は環境変数フラグ（既定 off/現行挙動）で gate。デプロイしても有効化するまで挙動は不変。フラグ一覧＝`MANIFEST.md`。
- **検証は本番非接触**: 各スクリプトは *ephemeral な使い捨て L1* と *隔離した Next dev（別treasury・別sqlite）* を立てて実チェーンで検証し、終了後に破棄する。本番 L1（127.0.0.1:8900）・本番 Turso・本番 treasury には一切触れない。
- **供給×価格**: 当面「ポイント+ソフト参照」モード。1e6 単位への切替と目標FDVは協調マイグレーション（`AGENT_LANE_from_FLOP.md` §18）。

## コードの所在
実コードは各サブプロジェクトに置く（そこで動くため）:
- `../morm-dashboard/` … `/api/lane/*`・`/api/admin/emit-nodes`・libs（units/price/valve/node-emission/lane-schema）
- `../morm-play/play_server.py` … 比例配分・view_by_other・署名付き視聴
このフォルダ = 取り組みのハブ（設計・検証・マニフェスト）。変更点の完全な列挙は `MANIFEST.md` を見る。

## 検証の回し方
```bash
cd verify && bash run_all.sh        # 全スイートを順に実行しpass/failを集計
# 個別: bash verify/phase2_node_run.sh 等
```
前提: `python3`（+`cryptography`）、`node`/`npx`、`morm-dashboard` の `node_modules` 導入済み。
