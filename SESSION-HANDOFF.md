# MORM セッション・ハンドオフ（2026-08-29）

**新セッションは最初にこれを読む。** 推奨 cwd = `~/Desktop/MORM/`。全体マップ=`ARCHITECTURE.md`／統合計画=`CONSOLIDATION-PLAN.md`／エアドロ=`agent-lane/DEPLOY.md`（冒頭★2026-08-29確定）。

## 一行サマリ
MORM 4サーフェス（www/api/node/play.morm.one）を監査→**致命セキュリティ封鎖・デプロイ済**／node.morm.one を**earned報酬(稼働+利用)に統一・デプロイ済**／リポ整理 Phase 1-3 完了（ARCHITECTURE・archive・論理コミット・旧0xダッシュ廃止・node-dashboard を submodule で1入口化）。**全てローカルcommit・MORM本体は未push**。残りをこのハンドオフの「残タスク」で片付ける。

## 稼働URL・ログイン（詳細=ARCHITECTURE.md）
- www.morm.one=`site/account.html`（walletless m0r）。api.morm.one=`morm-dashboard/`（ウォレットAPI＋Agent Lane API。旧0x UIは廃止済、`/`→node.morm.oneへ307）。node.morm.one=**`node-cluster/src/node-dashboard/`**（MCアカウント+PW）。play.morm.one=`morm-play/play_server.py`（Mac Mini）。L1=`morm-l1/` Mac Mini :8900（**不可侵**）。
- **admin PW: api.morm.one=`Yachida0024`（設定済）**。node.morm.one=別の既設PW（1234不可）。play=`ADMIN_TOKEN`。

## ★重要な罠
- **node.morm.one のデプロイ/実行実体は `~/Desktop/node-cluster/src/node-dashboard`**（`.env.local`/`.vercel`保持）。`MORM/node-dashboard` は submodule=参照専用（ここを編集してもデプロイされない）。編集/デプロイは node-cluster 側で。→ 新セッションで `request_directory ~/Desktop/node-cluster/src/node-dashboard`。
- Vercel デプロイ(`vercel --prod --yes`)は権限ガードで最初ブロック→ユーザー承認で通る。各 dir の `.vercel/project.json` がプロジェクトを決める（node-dashboard / morm-dashboard）。
- **secret厳守**: `.guardian-keys.env`/`.testnet-*.env`/`*.env`/plists/`service-key.json` は .gitignore 済。`git add .` 禁止・パス指定で add。
- 本番 L1 `127.0.0.1:8900` 書込みは fund-payouts 等の所定手順のみ。

## 完了済み（この一連）
- セキュリティ本番反映: **api.morm.one `/api/admin/send` 無認証treasury drain封鎖**・admin`1234`撤廃(→`Yachida0024`)／node.morm.one morm-distribute認証・heartbeat安全化・見込み30倍修正・ops earned化・payout二重防止。旧`/my`IDOR削除。
- node.morm.one: earned報酬(`app/lib/reward.js`)一本化・shop報酬レート表示一致・特商法実値化・ログイン堅牢化（30日期限/ロックアウト/列保証）。デプロイ済。
- account.html: 監査済（本番L1接続・faucet実払い確認）。
- リポ整理: `ARCHITECTURE.md`・`CONSOLIDATION-PLAN.md`・`_archive/`・`poc/`・論理コミット・両repo main マージ・node-dashboard submodule。
- Agent Lane: verify 9/9 PASS・統合モデル確定（node据置・⑤退役・3トラック追加）・payout口座(PLAY/DASH)検証（未付与・アドレス一致）。

## 残タスク（このセッションで全部片付ける）
### A. push（外向き・要ユーザー承認）
- `cd ~/Desktop/MORM && git push origin main`（MORM本体。node-dashboard main は push済）。ブランチ(`chore/*`)は任意。

### B. secret ローテ（履歴混入・要無効化）
- `morm-aiservice/service-key.json`（実ed25519 seed。untrack済だが履歴に残る）→ 鍵ローテ。
- `.claude/launch.json` の `--treasury-seed`（anvil/dev用らしい）→ 確認して除去/ローテ。

### C. 残セキュリティ（コード済/未・要ホスト反映）
- **play_server.py 他4 settle経路**(settle_referrals/_settle_fixed/_settle_proportional/settle_challenge)+ `_points_loop`自動配当 = `payout()`と同じ「予約先行+lock」を適用 → `agent-lane/verify/run_all.sh` で検証 → **Mac Mini へ転送＋`launchctl kickstart -k gui/$UID/com.morm.play`**。※`payout()`は修正済。
- **export_relayer.py**（修正済: last_block永続化+dust ALERT）→ **リレーヤ運用ホストへ反映**＋contractの`MIN_EXIT>=1e18`設定（1MORM未満exit永久損失の根本対策）。
- play: 読みIDOR(feed/content/mine/earnings/me)・ADMIN_TOKEN in URL→header化・mod preview 404・age自己申告。

### D. Phase 2 残
- 旧 `morm-dashboard/app/admin/*` の陳腐化ページ整理（※`/admin/ads`・`/admin/send` は Agent Lane で温存）。
- `morm-market/` のデプロイ先確定（market.morm.one 未live）。

### E. Agent Lane 活性化（`agent-lane/DEPLOY.md` 冒頭★の順）
- 前提: ①api.morm.one `ADMIN_PASSWORD`=Yachida0024（済）②**payout口座(PLAY/DASH)を fund**（`agent-lane/deploy/fund-payouts.md`・Mac Mini L1操作・base=1整数MORM）③base=1統一。
- 順序: A(不活性・既載) → C(換金バルブ) → **F(AD・発行外で安全)** → B(lane・cap必須) → D(engagement・要C[play settle修正]先行)。**Phase E(node emission)は廃止**。

## 必要アクセス（新セッションで request）
- `~/Desktop/node-cluster/src/node-dashboard`（node.morm.one 編集/デプロイ）
- SSH: Mac Mini（play/L1・fund・plist）／リレーヤ運用ホスト（export_relayer）。CLAUDE.md/メモリにSSH情報。

## メモリ参照
`reference_morm_security_audit_2026-08`／`project-morm-dashboard-login-rewards`／`reference_agent_lane_session_handoff`（別プロジェクトmemory・冒頭に★2026-08-29上書き済）。
