# MORM 統合プラン（Phase 3: モノレポ化）

作成: 2026-08-29。Phase 1（ARCHITECTURE.md・archive・secret防御・論理コミット）と Phase 2（旧0x運用ダッシュ廃止）は完了・main反映済み。本書は **Phase 3 = `node-cluster/src/node-dashboard`（node.morm.one 本体）を MORM 配下へ集約**の実行計画。

## Context（なぜ）
node.morm.one の本体が **MORM リポジトリの外**（`~/Desktop/node-cluster/src/node-dashboard`・独立git・Vercel `node-dashboard`）にあり、`IPPool-System/node-dashboard` から symlink 参照。これが最大の構造的分散で、過去に「本番と別アプリの取り違え」を招いた。1つの入口（MORM）から辿れる状態にする。

## 現状の依存（壊すと本番/運用が止まる箇所）
| 依存 | 内容 | 壊れると |
|---|---|---|
| Vercel project `node-dashboard` | `.vercel/project.json`（prj_qtcrFEmN…）が dir 内。CLI `vercel --prod` はこの dir から実行 | 誤ると node.morm.one デプロイ不能 |
| symlink | `IPPool-System/node-dashboard` → `node-cluster/src/node-dashboard` | IPPool側の参照が切れる |
| `scripts/fleet-poller.mjs` | dir ROOT の `.env.local`(TURSO/OPS_TOKEN) を読む・`DASH_URL` へ heartbeat POST | 稼働ゲージ/報酬が止まる |
| 独立git履歴 | node-dashboard 自身の commit 履歴（mc1025/1031/1063 等） | 移植方法次第で履歴消失 |
| ホスト分散 | poller は Mac Mini/hpmini 等で **その場の repo チェックアウト**を実行 | ローカル移動だけでは反映されない |
| `.env.local`/`.next`/`node_modules` | gitignore。移動先で再配置/再install が要 | ビルド不能 |

## 方式（2案）— ★推奨=A（低リスク）

### A. Git Submodule（物理移動せず“1入口”化・**推奨**）
`node-cluster/src/node-dashboard` を **MORM のサブモジュール** `MORM/node-dashboard` として登録。ファイルは動かさない＝Vercel `.vercel` も symlink も fleet-poller もそのまま。履歴も保持。MORM から `node-dashboard/` を辿れて「1リポジトリで全体を掌握」できる。
- 手順:
  1. node-dashboard 側を **push 済みリモートに**（例 `github.com/Kemonos0424/node-dashboard`）。※未リモートなら先に作成。
  2. MORM で `git submodule add <node-dashboard-remote-url> node-dashboard`（実体は `node-cluster/src/node-dashboard` のリモート）。
  3. `IPPool-System/node-dashboard` symlink を `MORM/node-dashboard` に張り替え（任意）。
  4. `.gitmodules` をコミット。
- ロールバック: `git submodule deinit -f node-dashboard && git rm node-dashboard`（実体は無傷）。
- 影響: **デプロイ配線・poller・symlink は不変**。最も安全。

### B. Git Subtree（真のモノレポ・履歴移植・高工数/高リスク）
node-dashboard を履歴ごと `MORM/node-dashboard` に取り込み、node-cluster 独立repoを退役。
- 手順:
  1. `git subtree add --prefix=node-dashboard <node-dashboard-remote> main`（履歴保持）。
  2. **Vercel `node-dashboard` の Root Directory を `node-dashboard/` に再設定**（Git連携時）。CLI運用なら `MORM/node-dashboard/.vercel/project.json` を配置し、そこから `vercel --prod`。
  3. `IPPool-System/node-dashboard` symlink → `MORM/node-dashboard` に張替え。
  4. **poller ホスト（Mac Mini/hpmini）で repo を新パスへ移行**＋`.env.local` 移設＋launchd/cron のパス修正。★本番稼働に直結＝メンテ枠で実施。
  5. `node_modules`/`.next` を新場所で再生成。旧 `node-cluster/src/node-dashboard` は `_archive` へ。
- ロールバック: 難（履歴移植後）。旧repoを一定期間保持し、Vercel/symlink/poller を元に戻せるよう手順を控える。
- 影響: デプロイ配線・poller・symlink すべて張替え。**メンテナンス枠必須**。

## 推奨ロードアウト
1. **まず A（submodule）で“1入口”化**（低リスク・即ロールバック可）。日常はこれで掌握性が上がる。
2. 真のモノレポが要るタイミング（CI統合・依存共有等）で **B を計画メンテ枠**で実施。B前提の準備＝node-dashboard のリモート整備・poller ホスト一覧の確定・メンテ時間の確保。

## 実行前チェック（Bを行う場合）
- [ ] node-dashboard の Git リモートを確定（現状ローカルのみなら push 先を用意）
- [ ] Vercel `node-dashboard` の deploy 方式（CLI or Git連携）を確認し Root 設定方針を決定
- [ ] poller 稼働ホストの一覧（Mac Mini / hpmini / …）と各 `.env.local`・launchd/cron パス
- [ ] メンテナンス枠（heartbeat 断＝稼働ゲージ0リセットの影響を織り込む）
- [ ] `.env.local`（TURSO/OPS_TOKEN 等 secret）は移設のみ・**コミットしない**（.gitignore 済）

## 検証（両案共通・実施後）
1. `vercel --prod`（node-dashboard）→ `Aliased: node.morm.one`。`/api/auth/member` 不正=401（500退行なし）、`/api/shop/price`=200。
2. fleet-poller を1周（`--once`）→ 対象ノードの `last_heartbeat` 更新・gauge 進行。
3. `IPPool-System/node-dashboard` から実体へ到達可（symlink 有効）。
4. MORM から `node-dashboard/`（submodule or subtree）を辿れる。
