# MORM Node Dashboard

PC クラスタ管理 & **MORM（m0r）トークンリワード** ダッシュボード。
`node-cluster/src/node-dashboard` を MORM リポジトリ配下に移植したもので、報酬トークンを
旧 CLT（Sepolia ERC-20）から **MORM L1 のネイティブトークン m0r** に置き換えてある。

- Next.js 14 (App Router)
- Turso / libsql (`@libsql/client`)
- プル型ノードエージェント（`scripts/agent/node-agent.sh`）でタスクをノード上で実行

## 構成

```
morm-dashboard/
  app/            # ルーティング / API（運営: /admin, 個人: /my）
  db/             # スキーマ + マイグレーション（migrate-v5.js まで）
  lib/            # libsql クライアント
  scripts/agent/  # ノードエージェント（curl + jq ポーリング）
  public/         # アイコン等
```

## セットアップ

```bash
cd morm-dashboard
npm install
cp .env.local.example .env.local   # ← Turso の URL / トークンを記入
npm run dev
```

`.env.local`（リポジトリには含めない）に接続情報を設定する。未設定なら
`db/dashboard.sqlite` のローカル SQLite にフォールバックする（`app/lib/db.js`）:

```
TURSO_DATABASE_URL=libsql://<your-db>.turso.io
TURSO_AUTH_TOKEN=<token>
```

### ローカル DB（Turso なしで動かす）

```bash
sqlite3 db/dashboard.sqlite < db/schema.sql   # 11 テーブル + 16 既定タスクを作成
npm run dev
```

`db/schema.sql` は v5 までのカラム（`command`/`timeout_sec`/`agent_token`、
`task_runs` のタイムスタンプ、統一済みの `weekly_snapshots`）を含む完全版。

### Turso（クラウド）+ Vercel デプロイ

Turso / Vercel いずれも本人アカウントでのログインが必要（このリポジトリには
資格情報を含めない）:

```bash
# 1. Turso にログインして専用 DB を作成（ライブ CLT デプロイとは分離）
turso auth login
turso db create morm-dashboard
turso db show morm-dashboard --url          # → TURSO_DATABASE_URL
turso db tokens create morm-dashboard       # → TURSO_AUTH_TOKEN

# 2. スキーマ適用 + 初期データ投入（.env.local に上記 2 値を入れてから）
node db/init-turso.js                        # schema.sql を Turso に適用
node db/seed-turso.js                        # ノード/タスク等の初期データ（任意）

# 3. Vercel へ環境変数を設定してデプロイ
vercel env add TURSO_DATABASE_URL
vercel env add TURSO_AUTH_TOKEN
# （実送金を有効化する場合は下記 MORM L1 の 3 変数も追加）
vercel --prod
```

## トークンモデル（CLT → MORM 完全置換）

- **表示**: 全 UI で「CLT」表記を **MORM / m0r** に変更済み。
- **内部 DB**: 残高台帳カラムも完全リネーム済み:
  - `nodes`: `clt_balance/clt_pending/clt_spent` → `morm_balance/morm_pending/morm_spent`
  - `tasks`: `clt_cost` → `morm_cost`
  - `weekly_snapshots`: `clt_amount` → `morm_amount`
  - スキーマ（`db/schema.sql`）・マイグレーション（`db/migrate-v2.js`）・全 API/UI で統一。
- **送金**: `app/api/admin/send/route.js` は **MORM L1 への実送金に対応**。
  `MORM_L1_RPC_URL` と `MORM_TREASURY_SEED`（+ `MORM_TREASURY_ADDRESS`）が
  設定されていれば、`app/lib/morm-l1.js` がトレジャリー鍵で `TRANSFER` tx
  （`kind=6`）に ed25519 署名して L1 ノードの `POST /tx` に送信する。署名前イメージは
  `morm-l1/morm_l1/tx.py` の `signing_bytes`（正規化 JSON）と完全一致する形で
  JS 側に再実装してあり、Python L1 と署名・送信者・アドレスがバイト単位で一致することを
  検証済み。環境変数が未設定なら従来どおり擬似 txHash の **シミュレーション**にフォールバック。
- **Claim**: `app/my/rewards/page.js` は MerkleDrop + MetaMask から
  「MORM L1 + パスキー署名」表記に変更。`app/api/my/claim/route.js` は
  `../morm-l1/reward-data` の週次スナップショット（任意・無ければ空）を参照。

## ノードエージェント

`scripts/agent/README.md` を参照。各ノードで以下を実行:

```bash
export DASHBOARD_URL=<this-deployment-url>
export NODE_ID=<node id>
export AGENT_TOKEN=<管理 → ノード管理 → エージェント設定 で取得>
export INTERVAL=30
bash scripts/agent/node-agent.sh
```

## 完了済み / TODO

- [x] **(a)** `weekly_snapshots` のスキーマ整合（`db/schema.sql` と読み取り側
      `app/admin/rewards/page.js` を、書き込み側の
      `week_label/wallet_address/total_score/morm_amount` に統一）
- [x] **(b)** ローカル DB 検証（`schema.sql` 適用 → リワード insert→read ラウンドトリップ →
      `npm run build`）。クラウド Turso + Vercel 手順は上記「デプロイ」節に記載
      （本人ログインが必要なため未実行）
- [x] **(c)** MORM L1 への実送金（`app/lib/morm-l1.js` + `admin/send`、env ゲート、
      単一ノード L1 で送金→残高反映を実機確認）
- [ ] トレジャリー残高監視 / 送金失敗時のリトライ・冪等性（nonce 競合対策）
- [ ] マルチシグ・トレジャリー（`morm-l1` の `MULTISIG_TX` 対応）での送金
