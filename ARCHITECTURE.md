# MORM — 正典アーキテクチャ・マップ（取り違え防止の起点）

最終更新: 2026-08-29。**新しいセッションは最初にこれを読む。** どのURLがどのソース/デプロイかを一意に固定する（過去、旧アプリを本番と取り違える事故があったため）。

## 稼働中サーフェス（正典＝これが本番）

| 公開URL | 何 | ソース（正典） | デプロイ |
|---|---|---|---|
| **www.morm.one** / morm.one | LP＋**ユーザー口座**（walletless m0r・passkey/生体）＋whitepaper | `site/`（gitignore・別配線） | Mac Mini へ scp（静的） |
| **api.morm.one** | ①**ウォレットAPI**（account.htmlが叩く `/api/wallet/*`・`/api/price`）②旧0xダッシュ`/my`+`/admin`（**陳腐化**） | `morm-dashboard/` | Vercel `morm-dashboard` |
| **node.morm.one** | **MORMNODE**（MCアカウント名+PWログイン・ノード運用者）＋`/shop`機体販売 | **`~/Desktop/node-cluster/src/node-dashboard/`**（別gitリポジトリ・**MORM外**。`~/Desktop/IPPool-System/node-dashboard` はここへのsymlink） | Vercel `node-dashboard` |
| **play.morm.one** | **MORM Play**（動画ディスカバリ＋配信元秘匿・自動ed25519ウォレット） | `morm-play/`（`play_server.py`） | Mac Mini launchd `com.morm.play` |
| L1 `127.0.0.1:8900` | MORM L1 ノード（**不可侵**・写込みは所定手順のみ） | `morm-l1/` | Mac Mini |
| （EVM↔MORM スワップ/ブリッジUI） | `MORM/USD 価格`・`ブリッジ&スワップ(Base Sepolia)` | `morm-market/`（app.html/index.html） | ※公開先未確定（market.morm.one 未live） |

⚠️ **`morm-dashboard`（api.morm.one）と `node-cluster/src/node-dashboard`（node.morm.one）は別アプリ・別Turso・別Vercel**。前者=旧「Node Dashboard/0x」＋ウォレットAPI、後者=現「MORMNODE/MC」。**node運用の作業は必ず node-cluster 側**。

## インフラ / ハブ（保持）

| ディレクトリ | 役割 |
|---|---|
| `morm-l1/` | L1ノード実装（Python）。crypto/tx/state/rpc。 |
| `morm-chain/` | Solidity（`MORMExportBridge.sol`・`GuardianMultisig.sol`・`WMORM.sol`＋test/script）。Base Sepolia ブリッジ。 |
| `relayer.py` / `export_relayer.py` | ブリッジ・リレーヤ（L1⇄Base wMORM）。リレーヤ運用ホストで常駐。 |
| `agent-lane/` | **Agent Lane（エアドロ経済レール）の設計ハブ**：README/DEPLOY/MANIFEST/verify。実コードは morm-dashboard＋morm-play に在る。冒頭の「★★2026-08-29確定更新」が最優先。 |
| `morm-core/` | コア共有ライブラリ。 |
| `morm-aiservice/` | AIサービス（`aiservice.py`）。※`service-key.json` は untrack済（鍵ローテ要）。 |
| `docker/`・`bin/`・`docs/`・`brand/` | 配布・ドキュメント・ブランド。 |

## 経済レール（Agent Lane）の統合モデル（2026-08-29確定）
- **ノード報酬 = node.morm.one の `earned`（稼働×0.5＋利用GB×0.1）が唯一の正**。旧 `node-emission`/`emit-nodes`（⑤・morm-dashboard）は**退役・活性化しない**。
- Agent Lane が担うのは**ノード以外の3トラック**（AIエージェント lane・Play engagement・AD）。全て m0r ウォレットへ着金＝account.html が共通UI。payout鍵は分離（`~/.morm-agentlane/`）。
- 詳細＝`agent-lane/DEPLOY.md`。

## node/IPPool ドメイン（web/経済とは別系統）
- `~/Desktop/node-cluster/` … node.morm.one 本体（`src/node-dashboard`）＋ノード基盤。
- `~/Desktop/IPPool-System/` … 住宅IPプロキシプールの仕様ハブ（`IPPOOL-SPEC.md`）＋symlink（node-dashboard→node-cluster）＋`morm-edge-fleet`＋scripts。
- `~/Desktop/mormnode-eval/` … 機体(SBC)適性 bench/soak スクリプト。
- `~/Desktop/morm-residential-edge/` … エッジ配信ソフト（edge/picker/scripts）。

## アーカイブ（旧・置換済み）
- `_archive/morm-player/` … 旧Web版（swap/shop/wallet/admin/HLS＋passkeyサーバ）。morm-play＋account.html＋node-dashboard shop に置換済み。デプロイ痕跡なし。
- `_archive/morm-node-shop/` … 機体販売の元画像。実アセットは node-dashboard/public へ移行済み。

## セキュリティ状態（2026-08-29）
封鎖済: api.morm.one `/api/admin/send` 無認証drain・admin既定`1234`（=`Yachida0024`へ）／node.morm.one 認証欠落。詳細＝メモリ `reference_morm_security_audit_2026-08`。残: play他4 settle経路・bridge MIN_EXIT・旧/my IDOR・**aiservice鍵ローテ（履歴混入）**。
